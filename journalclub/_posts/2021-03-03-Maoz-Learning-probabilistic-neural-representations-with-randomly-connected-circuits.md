---
layout: post
title:  "Learning probabilistic neural representations with randomly connected circuits (2020)"
category: journalclub
olddate: March 03, 2021
---
 
*Ori Maoz, Gasper Tkacik, Mohamad Saleh Esteki, Roozbeh Kiani, Elad Schneidman*. Proceedings of the National Academy of Sciences (2020) 
[(Proceedings of the National Academy of Sciences)](http://www.pnas.org/lookup/doi/10.1073/pnas.1912804117)
[(local cache)]({{site.url}}/journalclub/JCpapers/MaozRandom2019.pdf)

#### Abstract
The brain represents and reasons probabilistically about complex stimuli and motor actions using a noisy, spike-based neural code. A key building block for such neural computations, as well as the basis for supervised and unsupervised learning, is the ability to estimate the surprise or likelihood of incoming high-dimensional neural activity patterns. Despite progress in statistical modeling of neural responses and deep learning, current approaches either do not scale to large neural populations or cannot be implemented using biologically realistic mechanisms. Inspired by the sparse and random connectivity of real neuronal circuits, we present a model for neural codes that accurately estimates the likelihood of individual spiking patterns and has a straightforward, scalable, efficient, learnable, and realistic neural implementation. This model's performance on simultaneously recorded spiking activity of >100 neurons in the monkey visual and prefrontal cortices is comparable with or better than that of state-of-the-art models. Importantly, the model can be learned using a small number of samples and using a local learning rule that utilizes noise intrinsic to neural circuits. Slower, structural changes in random connectivity, consistent with rewiring and pruning processes, further improve the efficiency and sparseness of the resulting neural representations. Our results merge insights from neuroanatomy, machine learning, and theoretical neuroscience to suggest random sparse connectivity as a key design principle for neuronal computation.