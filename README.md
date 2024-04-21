# Eco-Routing
Netowrks Project by JTP JavRouter.

This project studies Eco-Routing Protocol (Eco-RP) and Green OSPF (GOSPF), two proposed protocols which modifies OSPF to better utilize energy.

### Installation
The code was tested on Python 3.12 with matplotlib, networkx, and numpy as specified in `Pipfile`.

# Eco-Routing Protocol (Eco-RP)
The code for Eco-RP simulation can be found in `EcoRoutingProtocol.ipynb`. Run all cells to view the experiment results, which are printed directly in the notebook.

Global variables of `sleep_threshold` (Eco-RP entity will attempt to sleep if traffic falls below this amount), `ref_bandwidth` (reference bandwidth for link cost calculation), `active_node_cost` (energy usage of an active router), and `active_link_cost` (energy usage of an active link) can be modified.

Random.seed has been set for reproducability of the reported results, but the seed can be changed to view different examples.

# Green OSPF (GOSPF)
The code for Eco-RP simulation can be found in `gospf.ipynb`.