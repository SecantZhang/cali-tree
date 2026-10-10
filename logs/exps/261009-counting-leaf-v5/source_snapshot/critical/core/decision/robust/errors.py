"""Actionable graph diagnostics without breaking ValueError callers."""


class GraphValidationError(ValueError):
    def __init__(self, code, message, *, node_id='', dependency_id='', relationship=''):
        super().__init__(message)
        self.code, self.node_id, self.dependency_id, self.relationship = code, node_id, dependency_id, relationship

    def to_dict(self):
        return {'code': self.code, 'message': str(self), 'node_id': self.node_id,
                'dependency_id': self.dependency_id, 'relationship': self.relationship}
