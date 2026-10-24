"""Check that authentication releases its database connection before returning."""

import ast
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "app" / "core" / "dependencies.py"


class AuthenticationSessionLifetimeTests(unittest.TestCase):
    def test_authentication_closes_session_before_route_can_use_user(self):
        source = ast.parse(SOURCE.read_text(encoding="utf-8"))
        function = next(
            node for node in source.body
            if isinstance(node, ast.FunctionDef) and node.name == "get_current_user"
        )
        function.decorator_list = []
        function.args.defaults = []
        function.args.args[0].annotation = None
        function.returns = None
        namespace = {}

        class Field:
            def __eq__(self, value):
                return value

        class User:
            id = Field()

        class Session:
            closed = False

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.closed = True

            def scalar(self, statement):
                self.assert_open()
                return types.SimpleNamespace(id="user-id", role="candidate")

            def assert_open(self):
                if self.closed:
                    raise AssertionError("database session closed before lookup")

        session = Session()
        namespace.update(
            SessionLocal=lambda: session,
            _trace_event=lambda *_args, **_kwargs: None,
            decode_access_token=lambda _: {"sub": "user-id"},
            User=User,
            select=lambda _: types.SimpleNamespace(where=lambda condition: condition),
        )
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
        user = namespace["get_current_user"](types.SimpleNamespace(credentials="synthetic"))
        self.assertTrue(session.closed)
        self.assertEqual((user.id, user.role), ("user-id", "candidate"))


if __name__ == "__main__":
    unittest.main()
