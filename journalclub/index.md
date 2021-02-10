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

Journal club meetings currently take place on Wednesdays at 2 pm in via Zoom (see email for link).

**Join the club** by joining the [SBU Computational Neuroscience Google Group](https://groups.google.com/d/forum/sbu-computational-neuroscience/join)

# 2020 Fall Schedule
- August 26th: Matt
- September 2nd: Diego Arribas
- September 9th: Ayesha Vermani
- September 16th: Conor McGrory
- September 23rd: Yuan Zhao
- September 30th: Tong Liang
- October 7th: Jake Crosser
- October 14th: Josue Nassar
- October 21st:  Xiaoyu Yang
- October 28th: Tianshu Li
- November 4th: Ian Jordan
- November 11th: No JC (Veteran's Day)
- November 18th: Siddharth Paliwal
- November 25th: No JC (Thanksgiving)
- December 2nd: Piotr Sokol
- December 9th: No JC (NeurIPS conference)

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
