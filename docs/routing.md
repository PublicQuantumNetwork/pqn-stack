# Routing

In PQN, routing occurs through classical and quantum network resources. Given any number of nodes, communication is 
always mediated across at least one router. A single router is responsible for a finite number of nodes 
proportional to its compute capacity, determined at initialization time. Analogues to BGP for inter-router 
communication has been planned, but will not be implemented during the first phase of this project.

## Local network structure

The PQN network consists of one router connected to multiple nodes, some of which contain and manage quantum 
resources. Executing a quantum protocol throughout the network depends on classical communication and execution of 
quantum protocols. In the specific case of the PQN, for instance, a _classical node_ at the Urbana Public Library 
sends  requests for the execution of an entangled pair production protocol. The events in the Kwiat lab that start from
the reception of the request to relaying the information about entanglement statistics provides a natural boundary 
defining a _quantum node_.

## Networks events

The PQN network carries three main types of packets:

* **Data-carrying packets:** transport classical outcomes after performing a quantum protocol or a classical 
  data transformation
* **Control packets:** metadata required to either control quantum hardware remotely with or without time constraints
* **Routing packets:** metadata that maintains, changes or restores network behavior

## Dispatch mechanism

All network elements implement a `dispatch` function that depends on the contents of a `Packet`. The dispatch 
ensures that routing information is adequately interpreted, and that the appropriate protocol is performed by the 
desired node or group of nodes. The sequence of events in this case is as follows:

1. **InstrumentProvider A** sends a packet to the router
2. The router determines the validity of the sender and the receiver
3. The router extracts the signature of the packet, and separates the implementation into data, control and routing 
   backplane functions
4. The router sends the packet to **InstrumentProvider B**
5. **InstrumentProvider B** executes code implementing classical or quantum functions
6. **InstrumentProvider B** prepares a response packet with `(source, destination)` being reversed from the original request
7. The router proceeds repeats steps 2-4
8. If the packet `hops` value is zero, no further routing happens

## Intents and requests

The following table enumerates example combinations of intent and request types.

| **Intent** | **Request** | **Description**                                                        |
|------------|-------------|------------------------------------------------------------------------|
| DATA       | MSR         | Return the results of a measurement performed on the receiving node    |
| CTRL       | CMD         | Perform a low-level command on the receiving node                      |
| RTNG       | REG         | Register the sending node into the current routing table with passcode |
| RTNG       | DEL         | Remove the sending node from the current routing table with passcode   |