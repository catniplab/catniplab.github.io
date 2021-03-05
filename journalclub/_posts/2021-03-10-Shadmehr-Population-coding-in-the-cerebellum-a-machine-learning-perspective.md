---
layout: post
title:  "Population coding in the cerebellum: a machine learning perspective (2020)"
category: journalclub
olddate: March 10, 2021
---
 
*Reza Shadmehr*. Journal of Neurophysiology (2020) 
[(Journal of Neurophysiology)](https://journals.physiology.org/doi/10.1152/jn.00449.2020)
[(local cache)]({{site.url}}/journalclub/JCpapers/shadmehr2020.pdf)

#### Abstract
The cerebellum resembles a feedforward, three-layer network of neurons in which the "hidden layer" consists of Purkinje cells (P-cells) and the output layer consists of deep cerebellar nucleus (DCN) neurons. In this analogy, the output of each DCN neuron is a prediction that is compared with the actual observation, resulting in an error signal that originates in the inferior olive. Efficient learning requires that the error signal reach the DCN neurons, as well as the P-cells that project onto them. However, this basic rule of learning is violated in the cerebellum: the olivary projections to the DCN are weak, particularly in adulthood. Instead, an extraordinarily strong signal is sent from the olive to the P-cells, producing complex spikes. Curiously, P-cells are grouped into small populations that converge onto single DCN neurons. Why are the P-cells organized in this way, and what is the membership criterion of each population? Here, I apply elementary mathematics from machine learning and consider the fact that P-cells that form a population exhibit a special property: they can synchronize their complex spikes, which in turn suppress activity of DCN neuron they project to. Thus complex spikes cannot only act as a teaching signal for a P-cell, but through complex spike synchrony, a P-cell population may act as a surrogate teacher for the DCN neuron that produced the erroneous output. It appears that grouping of P-cells into small populations that share a preference for error satisfies a critical requirement of efficient learning: providing error information to the output layer neuron (DCN) that was responsible for the error, as well as the hidden layer neurons (P-cells) that contributed to it. This population coding may account for several remarkable features of behavior during learning, including multiple timescales, protection from erasure, and spontaneous recovery of memory.