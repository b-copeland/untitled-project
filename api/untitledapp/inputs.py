"""
Checking what a request sends, in one place (issue #219).

The pages only send sensible values, but anyone can call the API with anything: a key that is not a unit, ``NaN``, a
list where a number belongs, a string where a flag belongs. Each of those once reached a document, and some made the
refresh fail on that kingdom every tick. A route reads every value it uses through one of these, and stores only what
they return, so nothing the request made up is written.

Each raises ``BadInput`` with a sentence for the player; ``create_app`` turns it into a 400 with that message.
"""
import math


class BadInput(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def body(request):
    """The JSON object a request sent, or BadInput."""
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        raise BadInput("Send the request as a JSON object")
    return data


def body_field(data, field):
    """``data[field]``, which must be a JSON object, or BadInput."""
    value = data.get(field) if isinstance(data, dict) else None
    if not isinstance(value, dict):
        raise BadInput(f"Send {field} as an object")
    return value


def number(value, name="value", minimum=None, maximum=None, integer=False, blank=None):
    """
    ``value`` as a finite number (an int if ``integer``), within ``minimum`` and ``maximum``. The pages send numbers as
    numbers or as strings from a box; an empty box (``""`` or None) is ``blank`` if given, else refused. A bool, a list,
    ``NaN`` or infinity is refused.
    """
    if value in ("", None) and blank is not None:
        return blank
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise BadInput(f"{name} must be a number")
    try:
        parsed = float(value)
    except ValueError:
        raise BadInput(f"{name} must be a number")
    if not math.isfinite(parsed):
        raise BadInput(f"{name} must be a number")
    if integer:
        if parsed != int(parsed):
            raise BadInput(f"{name} must be a whole number")
        parsed = int(parsed)
    if minimum is not None and parsed < minimum:
        raise BadInput(f"{name} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise BadInput(f"{name} must be at most {maximum}")
    return parsed


def flag(value, name="value"):
    """``value`` as a bool. Only true and false are accepted."""
    if not isinstance(value, bool):
        raise BadInput(f"{name} must be true or false")
    return value


def text(value, name="value", max_length=None, blank=None):
    """``value`` as a string of at most ``max_length`` characters."""
    if value is None and blank is not None:
        return blank
    if not isinstance(value, str):
        raise BadInput(f"{name} must be text")
    if max_length is not None and len(value) > max_length:
        raise BadInput(f"{name} must be at most {max_length} characters")
    return value


def one_of(value, options, name="value"):
    """``value`` if it is one of ``options``."""
    if not isinstance(value, (str, int)) or isinstance(value, bool) or value not in options:
        raise BadInput(f"{value!r} is not a valid {name}")
    return value


def keyed(values, allowed, name="value", **number_options):
    """
    A dict of ``allowed`` key to number, from a request's dict: every key must be one of ``allowed`` and every value a
    number as ``number`` checks it (with ``number_options``). Not a dict, or a key not allowed, is refused.
    """
    if not isinstance(values, dict):
        raise BadInput(f"Send the {name}s as an object")
    unknown = [key for key in values if key not in allowed]
    if unknown:
        raise BadInput(f"{unknown[0]!r} is not a valid {name}")
    return {key: number(value, name=f"{name} {key}", **number_options) for key, value in values.items()}


def ids(values, known, name="kingdom"):
    """The ids in ``values`` that are in ``known``, each once, as strings. Not a list is refused; unknown ids are
    refused too."""
    if not isinstance(values, list):
        raise BadInput(f"Send the {name}s as a list")
    out = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (str, int)) or str(value) not in known:
            raise BadInput(f"There is no {name} {value!r}")
        if str(value) not in out:
            out.append(str(value))
    return out
