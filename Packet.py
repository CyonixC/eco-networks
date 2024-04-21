import networkx as nx

class Packet:
    def __init__(self, length, content) -> None:
        self.length = length    # dummy length
        self.content = content
        self.header = {}
    
class LSA(Packet):
    LSDB = 0    # link state database
    LSCUP = 1   # link state cut update (cut an unnecessary link)
    LSGUP = 2   # link state graft update (reactivate a link)
    
    def __init__(self, length, lsa_type, origin_router_id, lsa_id, content) -> None:
        super().__init__(length, content)
        self.header["router_id"] = origin_router_id
        self.header["lsa_type"] = lsa_type
        self.header["id"] = lsa_id

class T1LSA(LSA):
    def __init__(self, type, origin_router_id, link_entries, lsa_id) -> None:
        super().__init__(0, type, origin_router_id, lsa_id, link_entries)

class LSCUP(LSA):
    def __init__(self, origin_router_id, link_id, lsa_id) -> None:
        content = {"link_id": link_id}
        super().__init__(0, self.LSCUP, origin_router_id, lsa_id, content)

class LSGUP(LSA):
    def __init__(self, origin_router_id, link_id, lsa_id) -> None:
        content = {"link_id": link_id}
        super().__init__(0, self.LSCUP, origin_router_id, lsa_id, content)
