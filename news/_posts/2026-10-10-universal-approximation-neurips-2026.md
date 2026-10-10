---
layout: post
title: Universal approximation over infinite time at NeurIPS 2026
category: news
featured: true
news_type: announcement
---

Abel's paper on universal approximation for dynamical systems has been accepted at NeurIPS 2026, and we will present the poster in Sydney on December 9!
He proved that Neural ODEs can approximate multistable dynamics, the basis of decision-making, rhythm generation, and analog memory, over the infinite time horizon.

Previous universal approximation theorems for dynamical systems held only on finite time windows, or only for systems with a globally stable equilibrium, which eventually forget their initial conditions.
A trained model can pass every finite-time test and still fail in the long run, in three ways:

- **B-type (basin) error:** near the boundary between two basins of attraction, a small error in the vector field sends trajectories to the wrong attractor, and the model settles to the wrong steady state.
- **P-type (phase) error:** a tiny mismatch in the period of a limit cycle accumulates without bound, and the oscillation drifts out of phase.
- **D-type (discretization) error:** continuous attractors are not structurally stable, so a generic perturbation collapses the continuum of memory states into isolated ones.

The theorems control each of them.
For structurally stable (Morse-Smale) systems, basin errors stay confined to a thin layer around the basin boundaries.
A localized correction matches the period of each limit cycle exactly, so no phase drift builds up.
A normally hyperbolic continuous attractor is approximated by a grid of discrete attractors spaced more finely than the error tolerance.
As a result, trajectories of the Neural ODE stay close to those of the target system for all time, except from a small set of initial conditions.
This also bounds the long-run average of training losses such as the mean squared error.

Abel's work spans both ends of the time scale.
His earlier papers, [Back to the Continuous Attractor](/bringing-back-continuous-attractors/) (NeurIPS 2024) and [Dynamical Archetype Analysis](https://arxiv.org/abs/2507.05505), connect the finite and the infinite with the emphasis on the finite: systems with categorically different asymptotic behavior can still behave alike over finite time.
This paper goes to the other extreme.

Ságodi, Á. and Park, I. M. (2026). Universal Approximation Theorems for Dynamical Systems with Infinite-Time Horizon Guarantees. NeurIPS 2026. [OpenReview](https://openreview.net/forum?id=JFUIDA4w6C), [arXiv](http://arxiv.org/abs/2602.08640)

## Poster at NeurIPS 2026, Sydney

Wednesday, December 9, 5:00-8:00 PM AEDT, Hall 1-4 ([NeurIPS page](https://neurips.cc/virtual/2026/loc/sydney/poster/153723))

Come find us!
