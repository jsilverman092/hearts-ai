class IllegalMoveError(ValueError):
    """Raised when a player attempts an illegal move."""


class InvalidStateError(RuntimeError):
    """Raised when game state invariants are violated."""


__all__ = ["IllegalMoveError", "InvalidStateError"]
