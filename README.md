# Eco-Routing
Netowrks Project by JTP JavRouter.

This project studies Eco-Routing Protocol (Eco-RP) and Green OSPF (GOSPF), two proposed protocols which modifies OSPF to better utilize energy.

### Installation
The code was tested on Python 3.12 with matplotlib, networkx, and numpy as specified in `Pipfile`. To install:
```
pipenv install
pipenv shell
```
Alternatively, download the dependencies directly with pip.

# Eco-Routing Protocol (Eco-RP)
The code for Eco-RP simulation can be found in `EcoRoutingProtocol.ipynb`. Run all cells to view the experiment results, which are printed directly in the notebook.

Global variables of `sleep_threshold` (Eco-RP entity will attempt to sleep if traffic falls below this amount), `ref_bandwidth` (reference bandwidth for link cost calculation), `active_node_cost` (energy usage of an active router), and `active_link_cost` (energy usage of an active link) can be modified.

Random.seed has been set for reproducability of the reported results, but the seed can be changed to view different examples.

# Green OSPF (GOSPF), Eco-RP and OSPF comparisons
Time=dependent implementations for GOSPF, Eco-RP and OSPF may be found in the following files:
- `Router.py` - contains implementations for routers, including GOSPF, OSPF and EcoRP specific implementations. Also contains implementations for the Link State Database, which is not used in the final implementation.
- `Packet.py` - contains implementations for messages which may be sent by the different implementations, including Link State Advertisements. Most of the LSAs are not used in the final implementation.
- `Link.py` - contains helper classes for links between routers, including protocol-specific implementations as well as provisions for measuring link usage statistics.
- `Network.py` - contains helper classes for managing a network of routers and links, including manual updating of router state databases and asynchronous polling of Routers and Links for measurement of data.

`comparisons.ipynb` - contains the code for the experiments.