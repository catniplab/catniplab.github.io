---
layout: default
title: Computational Neuroscience Journal
permalink: /journalclub/
---
## Computational and Theoretical Neuroscience Journal Club at Stony Brook University

![cookies and science](/images/cookie.jpg){: .center-image}

As the tools in experiments neuroscience are rapidly developing, this is an important time to consider the broad trends and aims of the computational/theoretical works that are born alongside them.  Our aim is to present and discuss papers that reflect these modern directions so that we may better understand how our own work fits into a global neuroscience picture. Some themes and topics that we hope to cover are:

* computational models of neural systems
* novel analysis tools for understanding neural recordings
* recent advances in theoretical neuroscience
* popular theories in neuroscience

Journal club meetings currently take place on Wednesdays at 2:30 pm in via Zoom (see email for link).

**Join the club** by joining the [SBU Computational Neuroscience Google Group](https://groups.google.com/d/forum/sbu-computational-neuroscience/join)

# 2021 Spring Schedule
- February 3rd: Giancarlo La Camera
- February 10th: Ayesha Vermani
- February 17th: Memming Park
- February 24th: No JC (COSYNE)
- March 3rd: Tong Liang
- March 10th: Piotr Sokol
- March 17th: Xiaoyu Yang
- March 24th: Jake Crosser
- March 31st: Yuan Zhao
- April 7th: Ian Jordan
- April 14th: Matthew Dowling
- April 21st: Siddharth Paliwal
- April 28th: No JC
- May 5th: Tianshu Li
- May 12th: Josue Nassar

[For a list of previously presented journal club papers go here](/jc_archive)
{% comment %}
You can pick or [**suggest papers**](https://www.google.com/url?q=https://docs.google.com/document/d/17SuoVIIDbCae5GnxSHGO5BW2zbVP6wBCbaGGfgFLAOQ/edit?usp%3Dsharing&sa=D&ust=1472068897083000&usg=AFQjCNF5f_dZMloe4l3jWOm_mhxe7utbqw) to be discussed.
{% endcomment %}

# Current Papers 
{% assign currentYear = site.time | date: '%Y' %}
{% assign prevYear = currentYear | minus: 1 %}


<div class="posts">
  {% for post in site.posts %}
	{% if post.categories contains 'journalclub' %}
            {% if post.olddate contains {currentYear} %}
                <article class="post">
                {{post.olddate}}
                <a href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a>
                </article>
             {% endif %}
             {% if post.olddate contains {prevYear} %}
                 <article class="post">
                 {{post.olddate}}
                 <a href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a>
                 </article>
            {% endif %}
	{% endif %}
  {% endfor %}
</div>
