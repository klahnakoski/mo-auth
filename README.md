# mo_auth

Auth0 authentication with session management for Flask

* This library also supports [Device authentication](https://github.com/klahnakoski/mo-auth/blob/dev/docs/device-flow.md)


## Overview

This library provides a server endpoint that accepts Auth0 Access Tokens (either opaque or jwt) and trades them for a Session Token with a limited lifespan. This is meant to work with single page applications (SPAs) that are able to acquire tokens on their own [using the PKCE flow](https://auth0.com/docs/flows/guides/auth-code-pkce/call-api-auth-code-pkce). 

This library does not use secret API keys.

## Configuration

### Session Configuration

The `flask_session` module is responsible for providing session specific values to the server-side application. It generates, and shares, a secret Session Token for use in subsequent requests. The session information is kept on the server side, and not exposed to the client. This module integrates with Flask session management, but does not use cookies. `setup_flask_session()` attaches a session interface to the Flask application.

> ** The Session Token is a secret, so it is expected  this library be used on encrypted chennels only, like https

    setup_flask_session(
        flask_app, 
        {
            "db": {
                "filename": "sessions.sqlite"
            },
            "table": "sessions",
            "cookie": {
                "inactive_lifetime": "hour",
                "max_lifetime": "month"
            }
        }
     )
     
* `db.filename` - file to store the session info (uses memory if missing) 
* `table` - name of the table in the database to store the session information 
* `cookie.max_lifetime` - Limit the duration that session is valid 
* `cookie.inactive_lifetime` - Limit how long session is valid if no requests are made

### Auth0 Configuration

The `Authenticator` class adds endpoints to a Flask app which verify Auth0 Access Tokens and creates a new session if validated. 

    Authenticator(
        flask_app,
        {
            "domain": "example.auth0.com",
            "api.identifier": "https://example.com/query",
            "endpoints": {
                "login": "authorize",
                "logout": "logout",
                "keep_alive": "ping"
            }
        },
        permissions,
        session_manager
     )

* `domain` - As defined in the Auth0 API
* `api.identifier` - As defined by Auth0 API
* `scope` - minimum scope required to access this API
* `endpoints.login` - the only endpoint that accepts Access Tokens
* `endpoints.logout` - call this endpoint to prematurely expire the session token
* `endpoints.keep_alive` - call this endpoint to inform the server that the session is still active

The `Authenticator` will make calls into the permissions system and session system to notify them of new users and new sessions. 

* `permissions.get_or_create_user(user_details)` - to create new authenticated users
* `session_manager.setup_session()` - to setup a new session for each user tha logs in
* `session_manager.make_cookie()` - The login endpoint will respond with a session object; which is done by this call.


## Usage

This library expects the client to acquire its own Access Token before accessing the protected endpoints. Please see [the PKCE authorization flow for SPA](https://auth0.com/docs/flows/guides/auth-code-pkce/call-api-auth-code-pkce) for more details. You may also inspect [the example SPA ](https://github.com/klahnakoski/auth0-spa) that works specifically with this library.

Once the client has an Access Token, it can be sent to the login endpoint.

    curl https://example.com/login  -H "Authorization=<AccessToken>"

The service will verify the Access Token with Auth0; this include receiving some identity information; which is further confirmed/elaborated with Mozilla IAM. 

The body of the response is a Session Token. The necessary parameter is the secret `value`; the other parameters are for the browser to construct a cookie for subequent requests, and are optional.

    {
        "session_id": "the_secret_session_token"
        "expires": "Oct 31, 2019",
        "inactive_lifetime": "30minute"
    }

The Session Token is valid until it expires. You can use it by adding it the Authorization request header

    curl https://example.com/query -H "Authorization=the_secret_session_token"  -d "..."

The Session Token lifetime is variable, depending on how much it is used. To keep the Session Token alive without performing any other actions, you can call a `auth0.endpoints.keep_alive` 

    curl https://example.com/ping -H "Authorization=the_secret_session_token" 

Once the session expires, a new Access Token must be used to `login`.



