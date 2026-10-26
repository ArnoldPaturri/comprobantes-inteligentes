class InvoiceAgentError(Exception):
    """Error base controlado por la aplicación."""


class ImageValidationError(InvoiceAgentError):
    pass


class ExtractionError(InvoiceAgentError):
    pass


class RepositoryError(InvoiceAgentError):
    pass


class RecordNotFoundError(RepositoryError):
    pass


class InvalidRecordStateError(InvoiceAgentError):
    pass


class DuplicateCodeError(RepositoryError):
    pass
