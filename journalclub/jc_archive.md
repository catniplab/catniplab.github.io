---
layout: page
title: Past Journal Club Papers
permalink: jc_archive/
---
## Past Journal Club Papers

If you are interested in previous years' journal club activity look below to see all of the interesting works we have covered in the past!

# Past Papers 

<div class="posts">
  {% for post in site.posts %}
	{% if post.categories contains 'journalclub' %}
            {% if post.olddate %}
                <article class="post">
                {{post.olddate}}
                <a href="{{ site.baseurl }}{{ post.url }}">{{ post.title }}</a>
                </article>
            {% endif %}
        {% endif %}
  {% endfor %}
</div>
