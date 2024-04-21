import time
import asyncio
import random

class Link:
    def __init__(self, bandwidth, delay = 0, loss_rate = 0) -> None:
        self.loss_rate = loss_rate
        self.bandwidth = bandwidth
        self.delay = delay
        self.terminal1 = None
        self.interface1 = None
        self.terminal2 = None
        self.interface2 = None
        self.active = True
        self.last_checkpoint = time.time()
        self.activity_since_checkpoint = 0
        self.dropped_packets = 0
    
    def __str__(self):
        return f"{self.terminal1}{self.terminal2}"

    def __eq__(self, link_id) -> bool:
        return str(link_id) == str(self) or str(link_id) == f"{self.terminal2}{self.terminal1}"

    def get_id(self):
        return str(self)

    def deactivate(self):
        self.active = False
    
    def activate(self):
        self.active = True

    def create_link(self, router1, interface1, router2, interface2):
        if self.terminal1 != None or self.terminal2 != None:
            raise RuntimeError(f"Link already has terminals. Please create a new link")
        self.terminal1 = router1
        self.terminal1._add_link(router2, interface1, self)
        self.interface1 = interface1
        self.terminal2 = router2
        self.terminal2._add_link(router1, interface2, self)
        self.interface2 = interface2
        self.activate()
    
    def sample_dropped_packets(self):
        return self.dropped_packets
    
    def get_link_throughput(self, reset_activity = True):
        throughput = self.activity_since_checkpoint
        if reset_activity and time.time() - self.last_checkpoint > 1:
            self.last_checkpoint = time.time()
            self.activity_rate = 0
            self.activity_since_checkpoint = 0
        return throughput

    def get_activity_rate(self, reset_activity = True):
        current_activity_rate = self.activity_since_checkpoint / self.bandwidth
        if reset_activity and time.time() - self.last_checkpoint > 1:
            self.last_checkpoint = time.time()
            self.activity_rate = 0
            self.activity_since_checkpoint = 0
        return current_activity_rate
    
    def opposite_terminal(self, terminal):
        """Return what router is on the opposite end of this link

        Args:
            terminal (Router): current end

        Raises:
            ValueError: if this is called with a router that is not connected to this link

        Returns:
            Router: router on the other end
        """
        if terminal not in (self.terminal1, self.terminal2):
            raise ValueError(f"Link {self.terminal1} - {self.terminal2} queried with a router which is not one of its terminals")
       
        return self.terminal1 if terminal == self.terminal2 else self.terminal2

    async def send(self, sending_router, packet):
        if not self.active: return
        
        if sending_router not in (self.terminal1, self.terminal2):
            raise ValueError(f"Link {self.terminal1} - {self.terminal2} asked to send with a router which is not on either of its ends")
        
        receiving_router = self.terminal1 if sending_router == self.terminal2 else self.terminal2
        receiving_interface = self.interface1 if sending_router == self.terminal2 else self.interface2
        
        # print(f"{sending_router} sending message to {receiving_router}...")

        if self.activity_since_checkpoint + packet.length > self.bandwidth:
            self.dropped_packets += 1
            return False

        self.activity_since_checkpoint += packet.length
        self.activity_rate = self.activity_since_checkpoint / self.bandwidth
        if time.time() - self.last_checkpoint > 1:
            self.activity_since_checkpoint = 0
            self.last_checkpoint = time.time()

        # Simulate delay
        if self.delay != 0:
            await asyncio.sleep(self.delay)

        # Randomly drop packets
        if random.random() < self.loss_rate:
            print(f"Packet lost from link {self.terminal1} - {self.terminal2}!")
            return False

        receiving_router.receive(packet, receiving_interface)

        return True