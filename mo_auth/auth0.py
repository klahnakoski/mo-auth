from flask import request, session, Response
from jose import jwt
from mo_threads.threads import register_thread

from mo_future import decorate, first
from mo_json import value2json
from mo_times import Date
from pyLibrary.env import http
from pyLibrary.env.flask_wrappers import cors_wrapper
from vendor.mo_logs import Log

DEBUG = False


def get_token_auth_header():
    """Obtains the access token from the Authorization Header
    """
    try:
        auth = request.headers.get("Authorization", None)
        bearer, token = auth.split()
        if bearer.lower() == "bearer":
            return token
    except Exception as e:
        pass
    Log.error('Expecting "Authorization = Bearer <token>" in header')


def requires_scope(required_scope):
    """
    Determines if the required scope is present in the access token
    """
    return required_scope in session.scope.split()


class Authenticator(object):
    def __init__(self, flask_app, auth0, permissions, session_manager):
        if not auth0.domain:
            Log.error("expecting auth0 configuration")

        self.auth0 = auth0
        self.permissions = permissions
        self.session_manager = session_manager

        # ATTACH ENDPOINTS TO FLASK APP
        endpoints = auth0.endpoints
        if not endpoints.login or not endpoints.logout or not endpoints.keep_alive:
            Log.error("Expecting paths for login, logout and keep_alive")

        _attach(flask_app, endpoints.login, self.login)
        _attach(flask_app, endpoints.logout, self.logout)
        _attach(flask_app, endpoints.keep_alive, self.keep_alive)

    def markup_user(self):
        # WHAT IS THE EMPLOY STATUS OF THE USER?
        pass

    def verify_opaque_token(self, token):
        # Opaque Access Token
        url = "https://" + self.auth0.domain + "/userinfo"
        response = http.get_json(url, headers={"Authorization": "Bearer " + token})
        DEBUG and Log.note("content: {{body|json}}", body=response)
        return response

    def verify_jwt_token(self, token):
        jwks = http.get_json("https://" + self.auth0.domain + "/.well-known/jwks.json")
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header["alg"]
        if algorithm != "RS256":
            Log.error("Expecting a RS256 signed JWT Access Token")

        key_id = unverified_header["kid"]
        key = first(key for key in jwks["keys"] if key["kid"] == key_id)
        if not key:
            Log.error("could not find {{key}}", key=key_id)

        try:
            return jwt.decode(
                token,
                key,
                algorithms=algorithm,
                audience=self.auth0.api.identifier,
                issuer="https://" + self.auth0.domain + "/",
            )
        except jwt.ExpiredSignatureError as e:
            Log.error("Token has expired", code=403, cause=e)
        except jwt.JWTClaimsError as e:
            Log.error(
                "Incorrect claims, please check the audience and issuer",
                code=403,
                cause=e,
            )
        except Exception as e:
            Log.error("Problem parsing", cause=e)

    @register_thread
    @cors_wrapper
    def login(self, path=None):
        """
        EXPECT AN ACCESS TOKEN, RETURN A SESSION TOKEN
        """
        now = Date.now().unix
        try:
            access_token = get_token_auth_header()
            # if access_token.error:
            #     Log.error("{{error}}: {{error_description}}", access_token)
            if len(access_token.split(".")) == 3:
                access_details = self.verify_jwt_token(access_token)
                session.scope = access_details["scope"]

            # ADD TO SESSION
            self.session_manager.setup_session(session)
            user_details = self.verify_opaque_token(access_token)
            session.user = self.permissions.get_or_create_user(user_details)
            session.last_used = now

            self.markup_user()

            return Response(
                value2json(self.session_manager.make_cookie(session)), status=200
            )
        except Exception as e:
            session.user = None
            session.last_used = None
            Log.error("failure to authorize", cause=e)

    @register_thread
    @cors_wrapper
    def keep_alive(self, path=None):
        now = Date.now().unix
        session.last_used = now
        return Response(status=200)

    @register_thread
    @cors_wrapper
    def logout(self, path=None):
        session.user = None
        session.last_used = None
        return Response(status=200)


def verify_user(func):
    """
    VERIFY A user EXISTS IN THE SESSION, PASS IT TO func
    """

    @decorate(func)
    def output(*args, **kwargs):
        # IS THIS A NEW SESSION
        now = Date.now().unix
        user = session.get("user")
        if not user:
            Log.error("must authorize first")

        session.last_used = now
        return func(*args, user=user, **kwargs)

    return output


def _attach(flask_app, path, method):
    """
    ATTACH method TO path IN flask_app
    """
    flask_app.add_url_rule(
        "/" + path.strip("/"),
        None,
        method,
        defaults={"path": ""},
        methods=["GET", "POST"],
        )
    flask_app.add_url_rule(
        "/" + path.strip("/") + "/",
        None,
        method,
        defaults={"path": ""},
        methods=["GET", "POST"],
        )
    flask_app.add_url_rule(
        "/" + path.strip("/") + "/<path:hash>",
        None,
        method,
        defaults={"path": ""},
        methods=["GET", "POST"],
        )


