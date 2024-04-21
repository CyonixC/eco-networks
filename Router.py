import asyncio
import networkx as nx
from Packet import T1LSA, LSA, LSCUP, LSGUP

class Router:
    def __init__(self, router_id: str, n_interfaces: int) -> None:
        self.router_id = router_id
        self.links = [None] * n_interfaces

    def _add_link(self, router, interface_no, link):
        if interface_no > len(self.links):
            raise ValueError(f"Specified interface number {interface_no} does not exist on router {self}")
        self.links[interface_no] = link
    
    def remove_link(self, interface_no):
        if interface_no > len(self.links):
            raise ValueError(f"Specified interface number {interface_no} does not exist on router {self}")
        link = self.links[interface_no]
        self.links[interface_no] = None
        return link
    
    def send(self, packet, interface_id):
        if interface_id > len(self.links):
            raise ValueError(f"Specified interface number {interface_id} does not exist on router {self}")
        link = self.links[interface_id]
        if link == None:
            raise ValueError(f"Attempting to send a packet on {interface_id} which is not connected on {self}")
        asyncio.ensure_future(link.send(self, packet))

    def receive(self, packet, interface_no):
        pass
        # print(packet.content)
    
    def broadcast_message(self, packet, exclude_interfaces = []):
        for interface_no in range(len(self.links)):
            if interface_no in exclude_interfaces: continue
            if self.links[interface_no] == None: continue
            
            self.send(packet, interface_no)

    def __str__(self) -> str:
        return self.router_id

class OSPFRouter(Router):
    # OSPF neighbour states. Only using DOWN and FULL for now
    DOWN = 0
    INIT = 1
    EXSTART = 2
    EXCHANGE = 3
    LOADING = 4
    FULL = 5

    ACTIVE = 0
    IDLE = 1
    SLEEP = 2
    
    def __init__(self, router_id: str, n_interfaces: int) -> None:
        super().__init__(router_id, n_interfaces)
        self.link_state_db = LinkStateDatabase(router_id)
        self.interface_status = [self.SLEEP] * n_interfaces
        self.neighbour_states = [self.DOWN] * n_interfaces
        self.neighbours_link_entries = [None] * n_interfaces
        self.lsa_id_counter = 0
    
    def _add_link(self, router, interface_no, link):
        super()._add_link(router, interface_no, link)
        self.link_state_db.graph.add_node(router.router_id)
        self.link_state_db.graph.add_edge(self.router_id, router.router_id, cost = self.link_cost(link.bandwidth), active=True)
        self.neighbour_states[interface_no] = self.FULL # don't do the other states for now
        self.interface_status[interface_no] = self.ACTIVE
        self.neighbours_link_entries[interface_no] = LinkEntry(router.router_id, self.router_id + router.router_id, self.link_cost(link.bandwidth))

    def remove_link(self, interface_no):
        link = super().remove_link(self, interface_no)
        self.neighbour_states[interface_no] = self.DOWN
        self.interface_status[interface_no] = self.SLEEP
        connected_router = link.opposite_terminal(self)
        self.link_state_db.remove_edge(self, connected_router)
    
    def send_message(self, target_router, packet):
        if str(target_router) == str(self):
            return
        packet.header["target_router"] = target_router
        self.route_message(packet, target_router)
    
    def route_message(self, packet, target_router):
        next_hop = self.link_state_db.find_shortest_path(target_router.router_id)[1]
        for intfc, link_entry in enumerate(self.neighbours_link_entries):
            if link_entry == None: continue
            if link_entry.router_id == next_hop:
                next_hop_interface = intfc
                # print(f"sending to {next_hop_interface}")
                self.send(packet, next_hop_interface)
                break

    def update_interface_statuses(self):
        for i, link in enumerate(self.links):
            if link == None: continue
            if not link.active:
                self.interface_status[i] = self.SLEEP
                continue
            if link.get_link_throughput() > 0.00001:
                self.interface_status[i] = self.ACTIVE
            else:
                self.interface_status[i] = self.IDLE

    def receive(self, packet, interface_no):
        super().receive(packet, interface_no)
        if isinstance(packet, LSA):

            if not isinstance(packet, T1LSA):
                # this is a GOSPF message
                return 2

            new_lsa = self.update_lsdb(packet)
            if new_lsa:
                self.broadcast_message(packet, [interface_no])
                return 1    # LSDB updated, might need to update MCST

        else:
            if packet.header["target_router"] == self.router_id:
                pass
                # print(f"Message received by {self}")
                # print(packet.content)
            else:
                self.route_message(packet, packet.header["target_router"])
            
            return 0
    
    def sync_lsdb(self, ls_graph):
        self.link_state_db.graph = ls_graph

    def update_lsdb(self, lsa_message):
        return self.link_state_db.update_db(lsa_message)

    def broadcast_LSA(self):
        entries = []
        for i, le in enumerate(self.neighbours_link_entries):
            if le == None: continue
            if self.interface_status[i] == False: continue
            entries.append(le)
        lsa = T1LSA(type=LSA.LSDB, origin_router_id=self.router_id, link_entries=entries, lsa_id=self.lsa_id_counter)
        self.lsa_id_counter += 1
        self.broadcast_message(lsa)
        
    @staticmethod
    def link_cost(bandwidth):
        # cost is inversely proportional to bandwidth
        return 1_000_000 / bandwidth

class GOSPFRouter(OSPFRouter):
    def __init__(self, router_id: str, n_interfaces: int, upper_threshold = 0.8, lower_threshold = 0.2) -> None:
        super().__init__(router_id, n_interfaces)
        self.interface_active = [False] * n_interfaces
        self.current_topo = nx.Graph()
        self.mcst = nx.Graph()
        self.lscup_db = {}
        self.lsgup_db = {}
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold
        self.interface_switches = 0
        self.interface_graft_time = [None] * n_interfaces
    
    def _add_link(self, router, interface_no, link):
        self.interface_active[interface_no] = True
        return super()._add_link(router, interface_no, link)
    
    def receive(self, packet, interface_no):
        if not self.interface_active[interface_no]: return

        status = super().receive(packet, interface_no)

        # Not a GOSPF packet
        if status == 0: return
        if status == 1: # packet made LSDB update
            self.mcst = nx.minimum_spanning_tree(self.link_state_db.graph, weight="cost")

        if status == 2:
            if isinstance(packet, LSCUP):
                self.process_lscup(packet, interface_no)

            if isinstance(packet, LSGUP):
                new = self.process_lsgup(packet, interface_no)
    
    def sync_lsdb(self, ls_graph):
        super().sync_lsdb(ls_graph)
        self.mcst = nx.minimum_spanning_tree(ls_graph, weight="cost")
    
    def get_switches(self):
        switches = self.interface_switches
        self.interface_switches = 0
        return switches
    
    def update_current_topo(self, current_topo):
        self.current_topo = current_topo
            
    def route_message(self, packet, target_router):
        # print(self.current_topo.nodes)
        next_hop = nx.shortest_path(self.current_topo, source=self.router_id, target=target_router.router_id)[1]
        for intfc, link_entry in enumerate(self.neighbours_link_entries):
            if link_entry == None: continue
            if link_entry.router_id == next_hop:
                next_hop_interface = intfc
                # print(f"sending to {next_hop_interface}")
                self.send(packet, next_hop_interface)
                break

    def check_link_status(self, reset_activity = True):
        for intfc, link in enumerate(self.links):
            if link == None or not link.active: 
                self.interface_status[intfc] = self.SLEEP
                continue
            ar = link.get_activity_rate(reset_activity)
            if ar < self.lower_threshold:
                if (str(link)[0], str(link)[1]) not in self.mcst.edges and (str(link)[1], str(link)[0]) not in self.mcst.edges:
                    lscup_msg = LSCUP(self.router_id, link.get_id, self.lsa_id_counter)
                    self.lsa_id_counter += 1
                    self.deactivate_link(intfc)
            elif ar > self.upper_threshold:
                for intfc2, link2 in enumerate(self.links):
                    if link2 == None: continue
                    if not self.interface_active[intfc2]:
                        lsgup_msg = LSGUP(self.router_id, link2.get_id, self.lsa_id_counter)
                        self.lsa_id_counter += 1
                        self.restore_link(intfc2)
                return
            
    def process_lscup(self, packet, interface_num):
        origin_router_id = packet.header["router_id"]
        packet_number = packet.header["id"]
        
        # A newer or identical entry is already logged
        if origin_router_id in self.lscup_db and self.lscup_db[origin_router_id] >= packet_number:
            return 

        self.broadcast_message(packet, exclude_interfaces=[interface_num])
        
        # If I own the link referred to in this message, cut it.
        self.lscup_db[origin_router_id] = packet_number
        if self.router_id in packet.content["link_id"]:
            for intfc, link in self.links:
                if link == str(packet.content["link_id"]):
                    print("interface deactivated, incrementing switch")
                    self.deactivate_link(intfc)
        
    
    def process_lsgup(self, packet, interface_num):
        origin_router_id = packet.header["router_id"]
        packet_number = packet.header["id"]
        
        # A newer or identical entry is already logged
        if origin_router_id in self.lscup_db and self.lscup_db[origin_router_id] >= packet_number:
            return False

        self.broadcast_message(packet, exclude_interfaces=[interface_num])
        
        # If I own the link referred to in this message, cut it.
        self.lsgup_db[origin_router_id] = packet_number
        if self.router_id in packet.content["link_id"]:
            for intfc, link in self.links:
                self.current_topo.add_edge(self.router_id, link.opposite_terminal(self), cost=OSPFRouter.link_cost(link.bandwidth))
                if str(link) == str(packet.content["link_id"]):
                    self.restore_link(intfc)
        
        return True
    
    def deactivate_link(self, interface_num):
        self.links[interface_num].deactivate()
        self.interface_active[interface_num] = False
        self.interface_switches += 1
    
    def restore_link(self, interface_num):
        self.links[interface_num].activate()
        self.interface_active[interface_num] = True
        self.interface_switches += 1
            
class LinkEntry:
    def __init__(self, router_id, link_id, cost):
        self.router_id = router_id
        self.link_id = link_id
        self.cost = cost

class LinkStateDatabase:
    def __init__(self, router_id) -> None:
        self.lsa_db = {}    # this will be indexed by router id for easy retrieval. Contains collected LSAs
        self.router_id = router_id
        self.graph = nx.Graph() # actual topology graph
        self.graph.add_node(router_id)
    
    def update_db(self, lsa_message: T1LSA):
        router_id =  lsa_message.header["router_id"]
        lsa_id = lsa_message.header["id"]
        if router_id in self.lsa_db and self.lsa_db[router_id].header["id"] >= lsa_id:
            # if a more recent LSA exists inside the database already, ignore this one.
            return False
        
        self.lsa_db[router_id] = lsa_message

        # now, update the graph
        if router_id in self.graph:
            # remove all edges except the one that I share with the router
            neighbour = False
            if (self.router_id, router_id) in self.graph.edges:
                neighbour = True
                data = self.graph.get_edge_data(self.router_id, router_id)
            self.graph.remove_node(router_id)
            if neighbour:
                self.graph.add_edge(self.router_id, router_id, **data)

        for link_entry in lsa_message.content:
            # if the link is with myself, skip adding it to the database
            if link_entry.router_id == self.router_id:
                continue

            self.graph.add_node(link_entry.router_id)
            self.graph.add_edge(router_id, link_entry.router_id, cost=link_entry.cost, active=True)
        
        # This was a new message, so broadcast it
        return True
    
    def find_shortest_path(self, target_router):
        return nx.shortest_path(self.graph, self.router_id, target_router)