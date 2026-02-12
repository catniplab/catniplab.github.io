---
layout: post
title: "Overdispersion means latent factors"
category: news
authors: "Memming Park and Hyungju Jeon"
---

*Information in spiking neurons on latent variables*

*Originally published on [Memming's Substack](https://memming.substack.com/p/overdispersion-means-latent-factors)*

---

How many neurons do we need to simultaneously record from a brain region to reliably estimate a 5 dimensional continuous latent trajectory? Which neurons are more informative about the latent variables, and which ones are useless? These are important questions in experimental design and assessing quality of datasets.

## Point Process Foundations

Point process observations, such as neural spike trains, are completely characterized by their conditional intensity function.

## Observation Model

Neural spiking follows a standard probabilistic model: y_i(t) ~ Poisson(exp(C_i x(t) + b_i)) where y represents spike counts, x(t) denotes latent processes, C is the loading matrix, and b is baseline firing rate.

## Core Research Question

Given neural spiking recordings, how much do the neurons inform us about the latent neural states? We address this using Fisher Information theory.

## Key Findings

**Fisher Information Application**: We derive an upper bound for the Signal-to-Noise Ratio (SNR) of the latent trajectories observed from spikes.

**Neuron Contribution Imbalance**: We found that the Fisher information is primarily dominated by a few neuron-latent pairs, indicating that only a subset of the neurons strongly contributes to the overall information about the latent states.

**Temporal Dynamics Matter**: The SNR depends heavily on whether dynamics change rapidly versus systems with slower dynamics, where neural activity evolves more gradually over time.

## Empirical Application

We applied our methods to monkey brain recordings from the Neural Latent Benchmark, specifically dorso-medial frontal cortex during timing tasks.

## Practical Implications

We conclude with methodology for determining how many neurons are required for reliable latent state reconstruction, providing guidance for experimental design through power-law extrapolation.

## References

- Daley & Vere-Jones (1988) on point process theory
- Zhao & Park (2017) on variational latent Gaussian processes
- Sohn & Jazayeri (2022) for the neural dataset

## Paper

Jeon, H., & Park, I. M. "Quantifying Signal-to-Noise Ratio in Neural Latent Trajectories via Fisher Information." *European Signal Processing Conference (EUSIPCO 2024)*, Lyon, France. [arXiv:2408.08752](https://arxiv.org/abs/2408.08752)
