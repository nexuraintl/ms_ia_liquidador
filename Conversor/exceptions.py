"""
Excepciones personalizadas para el modulo Conversor
SRP: Solo define las excepciones del modulo
"""


class ConversorTRMError(Exception):
    """Excepcion base para errores del conversor TRM"""
    pass


class TRMServiceError(ConversorTRMError):
    """Excepcion para errores de comunicacion con el servicio TRM"""
    pass


class TRMValidationError(ConversorTRMError):
    """Excepcion para errores de validacion de datos"""
    pass
