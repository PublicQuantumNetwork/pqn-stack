# PQN Packets

A _packet_ is the unit of communication between nodes in a quantum/classical network that can be sent, routed and 
received. One packet corresponds to a single request to execute a quantum protocol and obtain data from that 
instance execution. Packets can request outcomes from quantum protocols, or control sequences that configure the 
hardware to change the structure of the quantum network to perform other protocols.

Internally, Packets are implemented as a `dataclass`.

## Packet structure

Packet structure is defined by the following fields:

* intent: data carrying, control carrying, or routing
* request: specific type of request for the specified intent
* source: `(network, node)` pair from which the request originates
* destination: `(network, node)` pair to which the response should be issued
* hops: non-negative integer indicating the maximum number a packet can be sent
* payload: data carried by the packet

When the number of hops reach zero, it cannot be further sent across the network.

## Operations

Packets are mainly data objects. However, two simultaneous access methods are of interest:

1. Obtaining the signature for dispatching purposes
2. Obtaining routing information by the router

## Assumptions and constraints

* Packets are assumed to reach their destination reliably (i.e., no UDP equivalent)
* All package routing is handled by a router, no send-receive operations are allowed between quantum network nodes
* Defining new kinds of requests (i.e. protocols) in the network requires adding an entry into the `PacketRequest` 
  class inside `pqnstack.network`.


## Notes

1. BGP-like inter-network routing will not be implemented for v1.0