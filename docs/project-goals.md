# Project goals

This initiative between the PQN and NCSA intends to produce a robust software stack that accomplishes various 
project, scientific and engineering goals.

## Top-level goals

* Support the operation of the Public Quantum Network by refining existing control software and a new user 
interface that aligns with current project goals and future aspirations
* Implement a software stack that has the potential to satisfy scientific needs across quantum networks more generally in the future

## Engineering goals

1. Improve operational reliability and robustness by structuring code in ways that help detect sources of error and 
explain their effects across the quantum network
2. Provide a better separation of responsibilities across existing optics control code to minimize future change 
   when the network is reconfigured, or when more nodes are added
3. Introduce mechanisms and opportunities to monitor usage, health and status across quantum network operations
4. Build abstractions that are minimal, understandable by experimentalists, and stand the test of time as the 
   quantum network grows and complexifies
5. Write documentation that assists current and future lab members in the process of modifying and augmenting the 
   code, as well as describe the intent behind its underlying design choices
