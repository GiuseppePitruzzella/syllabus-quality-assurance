import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.auth import current_user
from app.database import Base
from app.main import app
from app.models.user import User


_AUTH_REALITY_TESTS = {"test_api_auth.py", "test_api_authorization.py"}


@pytest.fixture(autouse=True)
def _bypass_api_auth_for_legacy_api_tests(request):
    """Keep pre-auth API tests focused on their original behavior.

    Phase 11.B protects application routers through ``current_user``.
    Most existing endpoint tests are not about authentication, so they
    receive a synthetic user. The auth-specific tests opt out and
    exercise the real cookie/session boundary.
    """
    if request.node.path.name in _AUTH_REALITY_TESTS:
        yield
        return

    app.dependency_overrides[current_user] = lambda: User(
        id=1,
        email="test-user@example.com",
        full_name="Test User",
        role="quality_reviewer",
        is_active=True,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(current_user, None)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
