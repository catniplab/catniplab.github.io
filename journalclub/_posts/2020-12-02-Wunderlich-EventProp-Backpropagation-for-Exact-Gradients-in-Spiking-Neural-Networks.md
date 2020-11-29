---
layout: post
title:  EventProp: Backpropagation for Exact Gradients in Spiking Neural Networks (2020)
category: journalclub
olddate: December 02, 2020
---
 
*Timo C. Wunderlich, Christian Pehle*. arXiv:2009.08378 [cs, q-bio] (2020) 
[(arXiv:2009.08378 [cs, q-bio])](http://arxiv.org/abs/2009.08378)
[(local cache)]({{site.url}}/journalclub/JCpapers/wunderlichEventPropBackpropagationExact2020.pdf)

#### Abstract
We derive the backpropagation algorithm for spiking neural networks composed of leaky integrate-and-fire neurons operating in continuous time. This algorithm, EventProp, computes the exact gradient of an arbitrary loss function of spike times and membrane potentials by backpropagating errors in time. For the first time, by leveraging methods from optimal control theory, we are able to backpropagate errors through spike discontinuities and avoid approximations or smoothing operations. EventProp can be applied to spiking networks with arbitrary connectivity, including recurrent, convolutional and deep feed-forward architectures. While we consider the leaky integrate-and-fire neuron model in this work, our methodology to derive the gradient can be applied to other spiking neuron models. As errors are backpropagated in an event-based manner (at spike times), EventProp requires the storage of state variables only at these times, providing favorable memory requirements. We demonstrate learning using gradients computed via EventProp in a deep spiking network using an event-based simulator and a non-linearly separable dataset encoded using spike time latencies. Our work supports the rigorous study of gradient-based methods to train spiking neural networks while providing insights toward the development of learning algorithms in neuromorphic hardware.