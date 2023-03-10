"""Role related endpoints"""
from typing import List
import logging

import pendulum
from fastapi import APIRouter, Depends, Request
from starlette import status
from arkia11nmodels.models import Role, User
from arkia11nmodels.schemas.role import DBRole, RoleCreate
from arkia11nmodels.schemas.user import DBUser, UserList


from ..schemas.roles import RolePager
from ..schemas.users import UserPager
from ..helpers import get_or_404
from ..security import JWTBearer, check_acl


LOGGER = logging.getLogger(__name__)
ROLE_ROUTER = APIRouter(dependencies=[Depends(JWTBearer(auto_error=True))])


@ROLE_ROUTER.post("/api/v1/roles", tags=["roles"], response_model=DBRole, status_code=status.HTTP_201_CREATED)
async def create_role(request: Request, pdrole: RoleCreate) -> DBRole:
    """Create a new role"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:create")
    role = Role(**pdrole.dict())
    await role.create()
    refresh = await Role.get(role.pk)
    return DBRole.parse_obj(refresh.to_dict())


@ROLE_ROUTER.get("/api/v1/roles", tags=["roles"], response_model=RolePager)
async def list_roles(request: Request) -> RolePager:
    """List roles"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:read")
    roles = await Role.query.where(
        Role.deleted == None  # pylint: disable=C0121 ; # "is None" will create invalid query
    ).gino.all()
    if not roles:
        return RolePager(items=[], count=0)
    pdroles = [DBRole.parse_obj(role.to_dict()) for role in roles]
    return RolePager(
        count=len(pdroles),
        items=pdroles,
    )


# FIXME: Add patch method and pydanctic schema for uppdating
@ROLE_ROUTER.get("/api/v1/roles/{pkstr}", tags=["roles"], response_model=DBRole)
async def get_role(request: Request, pkstr: str) -> DBRole:
    """Get a single role"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:read")
    role = await get_or_404(Role, pkstr)
    return DBRole.parse_obj(role.to_dict())


@ROLE_ROUTER.delete("/api/v1/roles/{pkstr}", tags=["roles"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(request: Request, pkstr: str) -> None:
    """Delete role"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:delete")
    role = await get_or_404(Role, pkstr)
    await role.update(deleted=pendulum.now("UTC")).apply()


@ROLE_ROUTER.get("/api/v1/roles/{pkstr}/users", tags=["roles"], response_model=UserPager)
async def get_role_assignees(request: Request, pkstr: str) -> UserPager:
    """Get list of users assigned to role"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:read")
    # FIXME: actually paginate with DB cursor, the list method can get very expensive
    role = await get_or_404(Role, pkstr)
    users = await role.list_role_users()
    pdusers = [DBUser.parse_obj(user.to_dict()) for user in users]
    return UserPager(items=pdusers, count=len(users))


@ROLE_ROUTER.post("/api/v1/roles/{pkstr}/users", tags=["roles"], response_model=UserList)
async def assign_role(request: Request, pkstr: str, userids: List[str]) -> UserList:
    """Assign users this role, returns list of users added (if user is missing from list it already had role)"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:update")
    role = await get_or_404(Role, pkstr)
    # This will sadly mess things up for asyncpg with the way the gino middleware is set up
    # users = await asyncio.gather(*[get_or_404(User, userid) for userid in userids])
    lst = []
    for userid in userids:
        user = await get_or_404(User, userid)
        if await role.assign_to(user):
            lst.append(DBUser.parse_obj(user.to_dict()))
    return UserList(lst)


@ROLE_ROUTER.delete("/api/v1/roles/{pkstr}/users/{userid}", tags=["roles"], status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(request: Request, pkstr: str, userid: str) -> None:
    """Remove user from this role"""
    check_acl(request.state.jwt, "fi.pvarki.arkia11nmodels.role:update")
    role = await get_or_404(Role, pkstr)
    user = await get_or_404(User, userid)
    await role.remove_from(user)
