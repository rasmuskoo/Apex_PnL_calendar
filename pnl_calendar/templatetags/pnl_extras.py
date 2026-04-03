from django import template

register = template.Library()


@register.filter
def get_item(data, key):
    if data is None:
        return None
    return data.get(key)
