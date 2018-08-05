from functools import wraps


def retry_if_network_error(exception):
    return isinstance(exception, OSError)


def retry_if_network_error_or_parse_error(exception):
    return retry_if_network_error(exception) or isinstance(exception, (LookupError, ValueError, AttributeError))


def default_if_exception(default, logger=None, msg=""):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except:
                if logger:
                    message = msg
                    if not message:
                        message = "Exception occurred and default will be returned.".format(f.__str__())
                    message = "{}{}".format(message,
                                            "function: {}, args: {}, kwargs: {}".format(f.__str__(), args, kwargs))
                    logger.exception(message)
                return default

        return wrapper

    return decorator
