class ErrorAgenteComprobantes(Exception):
    """Error base controlado por la aplicación."""


class ErrorValidacionImagen(ErrorAgenteComprobantes):
    pass


class ErrorExtraccion(ErrorAgenteComprobantes):
    pass


class ErrorRepositorio(ErrorAgenteComprobantes):
    pass


class ErrorRegistroNoEncontrado(ErrorRepositorio):
    pass


class ErrorEstadoRegistro(ErrorAgenteComprobantes):
    pass


class ErrorCodigoDuplicado(ErrorRepositorio):
    pass
