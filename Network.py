import asyncio
import networkx as nx
from Router import OSPFRouter

class Network:
    def __init__(self) -> None:
        self.nodes = []
        self.links = []
        self.interfaces_active = {}
        self.throughput_energy_constant = 0.000_000_1
        self.active_interface_constant = 10
        self.idle_interface_constant = 8
        self.sleep_interface_constant = 0.16
        self.swap_state_constant = 20
        self.active_router_constant = 30
        self.router_switch_constant = 60
        self.link_states = {}
        self.network_state = nx.Graph()
        self._monitoring_loop = None
        self.energy_record = []
        self.drop_record = []
    
    def start_monitoring(self, interval=1):
        """Start monitoring the network state at a given interval.

        Args:
            interval (int, optional): Polling interval. Defaults to 1.
        """
        self.energy_record = []
        self.drop_record = []
        self._monitoring_loop = asyncio.ensure_future(self.monitor(interval))
    
    async def monitor(self, interval=1):
        """Monitor the network state at a given interval. Monitors energy and dropped packets.

        Args:
            interval (int, optional): Polling interval in seconds. Defaults to 1.
        """
        while True:
            self.energy_record.append(self.get_total_energy())
            self.drop_record.append(self.get_dropped_packets())
            await asyncio.sleep(interval)
        
    def stop_monitoring(self):
        """Stop monitoring the network and return the relevant data.

        Returns:
            Tuple(List[float], List[int]): Energy use and dropped packets data respectively.
        """
        self._monitoring_loop.cancel()
        return self.energy_record, self.drop_record
    
    def get_link_states(self):
        """Get the states (active or inactive) of all links in the network.

        Returns:
            List[bool]: list of link states
        """
        for link in self.links:
            self.link_states[link.get_id()] = link.active
        return self.link_states
    
    def update_interface_states(self):
        """Update the states of all interfaces in the network by calling the update_interface_statuses method of each node."""
        for node in self.nodes:
            node.update_interface_statuses()
            for i, activity in enumerate(node.interface_status):
                self.interfaces_active[f"{node}{i}"] = activity
            
    def get_network_state(self):
        """Create a map of the current network state, including inactive links.

        Returns:
            nx.Graph: graph representing the network state
        """
        network_state = nx.Graph()
        for node in self.nodes:
            network_state.add_node(node.router_id)
        for link in self.links:
            network_state.add_edge(link.terminal1.router_id, link.terminal2.router_id, cost=OSPFRouter.link_cost(link.bandwidth), capacity=link.bandwidth, active=link.active)
        
        return network_state
    
    def get_active_network_state(self):
        """Create a map of the current network state, using only active links.

        Returns:
            nx.Graph: graph representing the active network state
        """
        network_state = nx.Graph()
        for node in self.nodes:
            network_state.add_node(node.router_id)
        for link in self.links:
            if link.active:
                network_state.add_edge(link.terminal1.router_id, link.terminal2.router_id, cost=OSPFRouter.link_cost(link.bandwidth))
        
        return network_state

    def add_node(self, node):
        """Add a node to the network.

        Args:
            node (Router): new node
        """
        self.nodes.append(node)
    
    def add_link(self, link):
        """Add a link to the network. This link have been connected before adding it to the network.

        Args:
            link (Link): new link
        """
        self.links.append(link)
    
    def get_total_throughput(self, reset_activity=True):
        """Get total throughput of the network by summing the throughput of all links.

        Args:
            reset_activity (bool, optional): Whether to reset the throughput tracking after getting throughput. Defaults to True.

        Returns:
            int: total throughput of the network
        """
        total_throughput = 0
        for link in self.links:
            total_throughput += link.get_link_throughput(reset_activity)
        return total_throughput
    
    def calculate_interface_energy(self):
        """Get total energy consumption of all interfaces in the network.

        Returns:
            int: total energy consumption of all interfaces
        """
        sum_ = 0
        for activity in self.interfaces_active.values():
            if activity == OSPFRouter.ACTIVE: sum_ += self.active_interface_constant    
            elif activity == OSPFRouter.IDLE: sum_ += self.idle_interface_constant
            elif activity == OSPFRouter.SLEEP: sum_ += self.sleep_interface_constant
        return sum_
    
    def calculate_router_energy(self):
        """Get total energy consumption of all routers in the network.

        Returns:
            int: total energy consumption of all routers
        """
        sum_ = 0
        for _ in self.nodes:
            sum_ += self.active_router_constant
        return sum_
    
    def get_dropped_packets(self):
        """Get the total number of dropped packets in the network.

        Returns:
            int: number of dropped packets
        """
        sum_ = 0
        for link in self.links:
            sum_ += link.sample_dropped_packets()
        return sum_
    
    def get_total_energy(self, reset_activity=True):
        """Get the total energy consumption of the whole network.

        Args:
            reset_activity (bool, optional): Whether to reset tracking of throughput after getting. Defaults to True.

        Returns:
            float: energy consumption of the network
        """
        self.update_interface_states()
        throughput_energy = self.throughput_energy_constant * self.get_total_throughput(reset_activity)
        interface_energy = self.calculate_interface_energy()
        router_energy = self.calculate_router_energy()
        return throughput_energy + interface_energy + router_energy

class GOSPFNetwork(Network):
    def __init__(self) -> None:
        super().__init__()
    
    def calculate_interface_energy(self):
        """Get total energy consumption of all interfaces in the network, taking into account interface state switching.

        Returns:
            int: total energy consumption of all interfaces
        """
        sum_energy = super().calculate_interface_energy()
        for node in self.nodes:
            sum_energy += node.get_switches() * self.swap_state_constant
        return sum_energy

    def update_nodes_states(self):
        """Iterate through all nodes in the network to graft or cut links."""
        for node in self.nodes:
            node.check_link_status(reset_activity=False)
            node.update_current_topo(self.get_active_network_state())

    async def monitor(self, interval=1):
        while True:
            self.update_nodes_states()
            self.energy_record.append(self.get_total_energy())
            self.drop_record.append(self.get_dropped_packets())
            await asyncio.sleep(interval)

class EcoRPNetwork(Network):
    def __init__(self, lookback=5, sleep_threshold = 0.01, alpha=0.3, beta = 0.8) -> None:
        super().__init__()
        self.access_nodes = []
        self.utilisation_record = []
        self.alpha = alpha
        self.beta = beta
        self.lookback = lookback
        self.sleep_threshold = sleep_threshold
        self.max_cost = 1

    def add_access_node(self, node):
        """Add an access node to the network.

        Args:
            node (Router): new access node
        """
        super().add_node(node)
        self.access_nodes.append(node)

    def add_link(self, link):
        if OSPFRouter.link_cost(link.bandwidth) > self.max_cost:
            self.max_cost = OSPFRouter.link_cost(link.bandwidth)
            for l in self.links:
                l.default_cost = OSPFRouter.link_cost(l.bandwidth) / self.max_cost
        
        link.default_cost = OSPFRouter.link_cost(link.bandwidth) / self.max_cost

        return super().add_link(link)
    
    def get_network_state(self):
        """Create a map of the current network state, including inactive links.

        Returns:
            nx.Graph: graph representing the network state
        """
        network_state = nx.Graph()
        for i, node in enumerate(self.nodes):
            network_state.add_node(node.router_id, id_=i)
        for link in self.links:

            if link.get_link_throughput(reset_activity=False) > self.beta:
                # If the current link utilisation exceeds the maximum utilisation threshold, use the default cost
                network_state.add_edge(link.terminal1.router_id, link.terminal2.router_id, cost=link.default_cost, active=link.active)
                continue

            # otherwise, attempt to modify the cost
            id2 = network_state.nodes[link.terminal2.router_id]['id_']

            if id2 % 2 == 0:
                link_cost = self.adjust_cost(link.default_cost, self.alpha, False) # negative alpha
            else:
                link_cost = self.adjust_cost(link.default_cost, self.alpha, True)  # positive alpha

            network_state.add_edge(link.terminal1.router_id, link.terminal2.router_id, cost=link_cost, active=link.active)
        
        return network_state

    # def get_active_network_state(self):
    #     """Create a map of the current network state, using only active links.

    #     Returns:
    #         nx.Graph: graph representing the active network state
    #     """
    #     graph = super().get_active_network_state()
    #     for node in self.nodes:
    #         if not node.active and node.router_id in graph.nodes:
    #             graph.remove_node(node.router_id)
    #     return graph

    def adjust_cost(self, cost, alpha, odd):
        """Adjust the cost of a link based on the overall traffic history"""

        # Take the last lookback number of traffic rates
        traffic_rate = [i for i in self.utilisation_record[-self.lookback:]]

        x = range(len(traffic_rate))
        y = traffic_rate
        n = len(x)

        if n == 0:
            return cost

        x_mean = sum(x) / n
        y_mean = sum(y) / n
        try:
            slr = sum([(x[i] - x_mean) * (y[i] - y_mean) for i in range(n)]) / sum([(x[i] - x_mean)**2 for i in range(n)])
            if slr >= 0 and not odd:
                # Trending upwards, even node
                return max(cost - alpha * slr, cost)

            elif slr >= 0 and odd:
                # Trending upwards, odd node
                return min(cost + alpha * slr, cost)

            elif slr < 0 and not odd:
                # Trending downwards, even node
                new_cost = cost + alpha * slr, cost
            
            elif slr < 0 and odd:
                # Trending downwards, odd node
                new_cosst = cost - alpha * slr, cost
            
            return min(1, max(2 * cost - 1, new_cost))
                

        except ZeroDivisionError:
            return cost

    def update_nodes_states(self):
        """Iterate through all nodes in the network to update sleep status."""
        for node in self.nodes:
            node.update_router_status()
            node.sync_lsdb(self.get_active_network_state())

    async def monitor(self, interval=1):
        while True:
            self.update_nodes_states()
            self.utilisation_record.append(self.get_total_utilisation(reset_activity=False))
            self.energy_record.append(self.get_total_energy())
            self.drop_record.append(self.get_dropped_packets())
            await asyncio.sleep(interval)

    def get_total_utilisation(self, reset_activity=True):
        """Get total utilisation of the network by summing the utilisation of all links.

        Args:
            reset_activity (bool, optional): Whether to reset the throughput tracking after getting throughput. Defaults to True.

        Returns:
            float: total utilisation
        """
        total_throughput = 0
        active_graph = self.get_network_state()
        count = 0
        for link in self.links:
            if (link.terminal1.router_id, link.terminal2.router_id) in active_graph.edges:
                total_throughput += link.get_link_throughput(reset_activity) / link.bandwidth
                count += 1
        return total_throughput / count


    def calculate_router_energy(self):
        """Get total energy consumption of all routers in the network.

        Returns:
            int: total energy consumption of all routers
        """
        sum_ = 0
        for node in self.nodes:
            sum_ += self.active_router_constant * node.active
            sum_ += self.router_switch_constant * node.get_status_switches()
        return sum_
    
    def get_total_energy(self, reset_activity=True):
        """Get the total energy consumption of the whole network.

        Args:
            reset_activity (bool, optional): Whether to reset tracking of throughput after getting. Defaults to True.

        Returns:
            float: energy consumption of the network
        """
        self.update_interface_states()
        throughput_energy = self.throughput_energy_constant * self.get_total_throughput(reset_activity)
        interface_energy = self.calculate_interface_energy()
        router_energy = self.calculate_router_energy()
        return throughput_energy + interface_energy + router_energy