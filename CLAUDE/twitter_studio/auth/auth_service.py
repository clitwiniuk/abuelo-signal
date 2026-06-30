"""Authentication service — bridges twikit_client with the DB session log."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from database.schema import DBSession, SessionLocal
from models.user import UserModel
from services.tweet_service import map_user
from twikit_client.client import twitter_client, run
from utils.logger import logger


class AuthService:
    """Handles login flows and session persistence."""

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def try_cookie_login(self, language: str = "en-US") -> bool:
        """Attempt to restore session from cookies (sync wrapper for Streamlit)."""
        result = run(twitter_client.login_with_cookies(language=language))
        if result:
            self._record_session(twitter_client.me.screen_name if twitter_client.me else "unknown")
        return result

    def login(
        self,
        username: str,
        email: str,
        password: str,
        language: str = "en-US",
    ) -> bool:
        """Login with credentials (sync wrapper for Streamlit)."""
        result = run(
            twitter_client.login(
                username=username,
                email=email,
                password=password,
                language=language,
            )
        )
        if result:
            self._record_session(username)
        return result

    def logout(self) -> None:
        self._close_session()
        twitter_client.logout()

    # ------------------------------------------------------------------
    # Current user
    # ------------------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return twitter_client.is_authenticated

    def get_current_user(self) -> Optional[UserModel]:
        if twitter_client.me is None:
            return None
        return map_user(twitter_client.me)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------
    def _record_session(self, username: str) -> None:
        try:
            db = SessionLocal()
            # Deactivate any prior open sessions
            db.query(DBSession).filter(DBSession.active == True).update(
                {"active": False, "logged_out_at": datetime.utcnow()}
            )
            db.add(DBSession(username=username, active=True))
            db.commit()
            db.close()
        except Exception as exc:
            logger.warning(f"Session DB record failed: {exc}")

    def _close_session(self) -> None:
        try:
            db = SessionLocal()
            db.query(DBSession).filter(DBSession.active == True).update(
                {"active": False, "logged_out_at": datetime.utcnow()}
            )
            db.commit()
            db.close()
        except Exception as exc:
            logger.warning(f"Session DB close failed: {exc}")


auth_service = AuthService()
