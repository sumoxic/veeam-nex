"""创建/重置平台管理员账号。

用法：
    python scripts/bootstrap_admin.py --username admin --password 'Admin@12345'
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.security.passwords import hash_password, password_strength_error  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="创建或重置平台管理员")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin@12345")
    parser.add_argument("--email", default=None)
    parser.add_argument("--reset", action="store_true", help="用户已存在时重置口令")
    args = parser.parse_args()

    error = password_strength_error(args.password)
    if error:
        print(f"口令不合规: {error}", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is not None:
            if not args.reset:
                print(f"用户 {args.username} 已存在，如需重置口令请加 --reset", file=sys.stderr)
                return 1
            user.password_hash = hash_password(args.password)
            user.role = UserRole.ADMIN
            user.is_active = True
            db.commit()
            print(f"已重置管理员 {args.username}")
            return 0

        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            role=UserRole.ADMIN,
            email=args.email,
            display_name=args.username,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"已创建管理员 {args.username}（初始口令请尽快修改）")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
