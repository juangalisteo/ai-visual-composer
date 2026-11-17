def require_value(data, key, path):
    if not isinstance(data, dict):
        raise TypeError(
            f"La configuración {path.rsplit('.', 1)[0]} "
            "debe ser un diccionario."
        )
    if key not in data:
        raise ValueError(
            f"Falta la configuración obligatoria: {path}."
        )
    return data[key]


def require_mapping(data, key, path):
    value = require_value(data, key, path)
    if not isinstance(value, dict):
        raise TypeError(
            f"La configuración {path} debe ser un diccionario."
        )
    return value


def require_bool(data, key, path):
    value = require_value(data, key, path)
    if not isinstance(value, bool):
        raise TypeError(
            f"La configuración {path} debe ser booleana."
        )
    return value


def require_int(data, key, path):
    value = require_value(data, key, path)
    if isinstance(value, bool):
        raise TypeError(
            f"La configuración {path} debe ser un entero."
        )
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"La configuración {path} debe ser un entero válido."
        ) from error


def require_float(data, key, path):
    value = require_value(data, key, path)
    if isinstance(value, bool):
        raise TypeError(
            f"La configuración {path} debe ser numérica."
        )
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"La configuración {path} debe ser numérica."
        ) from error


def require_text(data, key, path):
    value = require_value(data, key, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"La configuración {path} debe contener texto."
        )
    return value.strip()


def require_sequence(data, key, path):
    value = require_value(data, key, path)
    if not isinstance(value, (list, tuple)):
        raise TypeError(
            f"La configuración {path} debe ser una lista."
        )
    return value
