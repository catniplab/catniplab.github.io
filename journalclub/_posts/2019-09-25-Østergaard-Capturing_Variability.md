---
layout: post
title:  Capturing Spike Variability in Noisy Izhikevich Neurons Using Point Process Generalized Linear Models (2017)
category: journalclub
olddate: September 25, 2019
---
 
*Jacob Østergaard, Mark A. Kramer, Uri T. Eden*. Neural Computation (2017) 
[(Neural Computation)](https://doi.org/10.1162/neco_a_01030)
[(local cache)]({{site.url}}/journalclub/JCpapers/Capturing_Variability.pdf)

#### Abstract
To understand neural activity, two broad categories of models exist: statistical and dynamical. While statistical models possess rigorous methods for parameter estimation and goodness-of-fit assessment, dynamical models provide mechanistic insight. In general, these two categories of models are separately applied; understanding the relationships between these modeling approaches remains an area of active research. In this letter, we examine this relationship using simulation. To do so, we first generate spike train data from a well-known dynamical model, the Izhikevich neuron, with a noisy input current. We then fit these spike train data with a statistical model (a generalized linear model, GLM, with multiplicative influences of past spiking). For different levels of noise, we show how the GLM captures both the deterministic features of the Izhikevich neuron and the variability driven by the noise. We conclude that the GLM captures essential features of the simulated spike trains, but for near-deterministic spike trains, goodness-of-fit analyses reveal that the model does not fit very well in a statistical sense; the essential random part of the GLM is not captured.