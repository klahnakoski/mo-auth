# mo_auth

Auth0 authentication with session management for Flask

## Overview

Supports a server endpoint that accepts Auth0 access tokens (either opaque or jwt) and trades them for a session token (a cookie) with given lifespan.

## Configuration

### Session Configuration

The `flask_session` module is responsible for providing session specific values to the application. It uses a secret browser cookie to lookup session information for each request.  The session information is kept on the server side, and not exposed to the client.  This module integrates with Flask session management: `setup_flask_session()` attaches a session interface to the Flask application.


    setup_flask_session(
        flask_app, 
        {
            "db": {
                "filename": "sessions.sqlite"
            },
            "table": "sessions",
            "cookie": {
                "name":"annotation_session",
                "domain": "example.com",
                "path": "/",
                "secure": false,
                "httponly": false,
                "inactive_lifetime": "hour",
                "max_lifetime": "month"
            }
        }
     )
     
These parameters override some of the Flask parameters of similar name    

|            Name           |   Flask variable      |  Description  |
|---------------------------|-----------------------|---------------|
| db.filename               |                       | file to store the session info (uses memory if missing) |
| table                     |                       | name of the table in the database to store the session information |
| cookie.name               | SESSION_COOKIE_NAME | Name of the cookie
| cookie.domain             | SESSION_COOKIE_DOMAIN | Limit host which cookie is sent |
| cookie.path               | SESSION_COOKIE_PATH | Limit path which the cookie is sent |
| cookie.httponly           | SESSION_COOKIE_HTTPONLY | Ensure javascript can not see cookie |
| cookie.secure             | SESSION_COOKIE_SECURE | Ensure cookie only sent encrypted |
| cookie.max_lifetime       | PERMANENT SESSION_LIFETIME | Limit the duration that session is valid |
| cookie.inactive_lifetime  |                        | Limit how long session is valid if no requests are made |



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

* **domain** - As defined in the Auth0 API
* **api.identifier** - As defined by Auth0 API
* **scope** - minimum scope required to access this API
* **endpoints.login** - the only endpoint that accepts Access Tokens
* **endpoints.logout** - call this endpoint to prematurely expire the session token
* **endpoints.keep_alive** - call this endpoint to inform the server that the session is still active

The `Authenticator` will make calls into the permissions system and session system to notify them of new users and new sessions. 

* `permissions.get_or_create_user(user_details)` - to create new authenticated users
* `session_manager.setup_session()` - to setup a new session for each user tha logs in
* `session_manager.make_cookie()` - The login endpoint will respond with a session object; which is done by this call.

### Device Authentication (server side)

"Devices" are hardware, or software, that do not have access to a browser.  The `Authenticator` will support device authentication.  

    Authenticator(
        flask_app,
        {
            ...                
            "device": {
                "db": {
                    "filename": null
                },
                "table": "device",
                "home": "http://dev.localhost:3000",
                "endpoints": {
                    "register": "annotation/device",
                    "status": "annotation/device_status",
                    "login": "annotation/device_login",
                    "callback": "annotation/device_callback"
                },
                "auth0": {
                    "domain": "dev-8821kz09.auth0.com",
                    "client_id": "FYlBPbNm7vZi9YPwVFyR7J2TLKrzNtST",
                    "redirect_uri": "http://dev.localhost:3000/annotation/device_callback",
                    "audience": "https://locahost/query",
                    "scope": "openid email query:send"
                }
            }
            ...
        }
    )
     
The device parameters are:

* **db.filename** - Filename for the SQLite database. Use memory if missing, or null. 
* **table** - The name of the file that connects the device to the user
* **home** - must know where it is, so it can construct URLs for Auth0
* **endpoints.register** - Used by the device to ask for authentication
* **endpoints.status** - Used by the device to see if the Human has authorized yet
* **endpoints.login** - Used by the Human (with browser) to start login process
* **endpoints.callback** - Used by Human to finish the login process
* **auth0.domain** - This authenticator is a client of Auth0, so it must know the Auth0 domain name
* **auth0.client_id** - Specific API ID
* **auth0.redirect_uri** - Full URL to complete the login process 
* **auth0.audience** - Auth0 audience
* **auth0.scope** - Auth0 scope
       
### Device Authentication (client side)

This library includes the client-side module for browserless "devices":

    Auth0Client({
        "service": "http://dev.localhost:3000",
        "rsa": {"bits": 512},
        "cookie": {
            "name": "annotation_session"
        },
        "endpoints": {
            "register": "annotation/device",
            "status": "annotation/device_status"
        }
    })

Parameters are:

* **service** - URL to the matching service this client will be connecting to
* **rsa.bits** - Number of bits to use for signing requests
* **cookie.name** - The name of the cookie used for tracking the session 
* **endpoints.register** - Path to used to start authentication
* **endpoints.status** - Path used to poll for login status


## Usage

This library expects the Javascript client to acquire its own Access Token before accessing the protected endpoints.  Please see [the PKCE authorization flow for SPA](https://auth0.com/docs/flows/guides/auth-code-pkce/call-api-auth-code-pkce) for more details. You may also inspect [the example SPA ](https://github.com/klahnakoski/auth0-spa) that works specifically with this library.

Once the client has an Access Token, it can be sent to the login endpoint.

    curl https://example.com/login  -H "Authorization=Bearer <AccessToken>"

The service will verify the access token with Auth0; this include receiving some identity information; which is further confirmed/elaborated with Mozzila IAM. 

The body of the response is a Session Token. The necessary parameter is the secret `value`; the other parameters are for the browser to construct a cookie for subequent requests, and are optional.

    {
        "name": "cookie name"
        "value": "the secret session token"
        "domain": "example.com",
        "path": "/",
        "secure": true,
        "httponly": true,
        "expires": "Oct 31, 2019",
        "inactive_lifetime": "30minute"
    }

The Session Token is valid until it expires. You can use it by adding it the request header, as a cookie

    curl https://example.com/query -H "Cookie=the secret session token"  -d "..."

The Session Token lifetime is variable, depending on how much it is used. To keep the Session Token alive without performing any other actions, you can call a `auth0.endpoints.keep_alive` 

    curl https://example.com/ping  -H "Cookie=the secret session token" 

Once the session expires, a new Access Token must be used to `login`.



### Device Authentication flow

The device authentication flow can be split into the Device potion and the Human portion.

**Register a new device**

All requests sent by the Device will be signed with a private RSA key. This means the requests will all look similar:

```
{
    "data": "eyJwdWJsaWNfa2V5Ijp7ImUiOjY1NTM3LCJuIjoi...",
    "signature": "cOOEreKnASAnlofDjdSo3Nysfok3yvR/hnouo..."
}
```

Since this format is inhumane, we will only discuss the content of the `data`.  In this case, the client wil register the Device:

```
{
    "public_key": {
        "e": 65537,
        "n": "08uzCfojGT/3woAiQwnzc9GegI0OGO+oq1qB4sPhFmycbOO1WfA1sq4kmXecXO1JgRZPhN4RvB2QSGyA/nGuZQ=="
    },
    "timestamp": 1573081713.6657598
}
```

This `public_key` will be used by the server to confirm the same Device is making subsequent requests. The `timestamp` ensures the request is valid for only a short time.

**Respond with URL**

When the Authenticator receives a registration request, it will respond with a URL for the Human (with a browser) to authenticate. Other information includes: When this registration attempt expires, how often to poll for an update, and as session_id for subsequent requests.

```
{
    "expiry": 1573082667.0485039,
    "interval": "5second",
    "session_id": "bq7w5KY/ow8/F4nHIBwwRLMgMSY/VparqZLJtb5Q",
    "url": "http://dev.localhost:3000/annotation/device_login?state=2N8hk9GC4mHg82RH8mex"
}
```

The server will also send `Set Cookie name=<session_id>` in the response header. It is important that this cookie be used for all subsequent calls because it will eventually be authenticated.
 
**Show URL to Human**

The Device client will show the URL to the Human so that he can open a browser. This client library will show the URL (for cut-and-paste), and it will show the URL as a QR code so that a mobile phone can be used.

**Request status, repeat**

The Device client will enter a loop, polling the Authenticator for status until there is success, failure, or a timeout.  Here is an example of the **unsigned** request body:

```
# POST to http://dev.localhost:3000/annotation/device_status
{
    "session": "bq7w5KY/ow8/F4nHIBwwRLMgMSY/VparqZLJtb5Q",
    "timestamp": 1573082605.4465632
}
```

And here is an example response from the Authenticator:

```
# Response from http://dev.localhost:3000/annotation/device_status
{
    "status": "still waiting",
    "try_again": true
}
```

**Human login**

The Authenticator provides a URL, and the Device client shows that URL to the Human. The following steps are between the Authenticator, Auth0, and the Human.  Meanwhile the Device continues to poll the Authenticator for an update.

**Open browser with URL**

The URL must be opened in a browser. Either the link can be cut-and-pasted to browser, or the QR code can be used to navigate to the URL with a mobile phone.

     http://dev.localhost:3000/annotation/device_login?state=2N8hk9GC4mHg82RH8mex

**Server forwards to Auth0**

The Authenticator will confirm the `state` exists, and establish a session for the Human portion of this flow. It will create a `code_verifier` secret, and hang onto it [as per PKCE flow](https://auth0.com/docs/flows/guides/auth-code-pkce/call-api-auth-code-pkce). Here is an example of the redirect URL, with some whitespace added for clarity:

    https://dev-8821kz09.auth0.com/authorize
        ?client_id             = FYlBPbNm7vZi9YPwVFyR7J2TLKrzNtST
        &redirect_uri          = http%3a%2f%2fdev.localhost%3a3000%2fannotation%2fdevice_callback
        &state                 = 2N8hk9GC4mHg82RH8mex
        &nonce                 = 3Uu8yX_LCeXcdquHaNuU8WThGQtWnend6Nw0P575iAo
        &code_challenge        = PMkht4EnhZnuTZyiY577h51X2v5-IAncFg3O0CUs7hg
        &response_type         = code
        &code_challenge_method = S256
        &response_mode         = query
        &audience              = https%3a%2f%2flocahost%2fquery
        &scope                 = openid%20email%20query%3asend

**Human authentication**

The Human will navigate the authentication screens of the Auth0, and the third party. The Authenticator and the Device know nothing about this process.
  
**Server gets callback**

After the Human and third parties have agreed authentication has happened, Auth0 will redirect the browser to the `callback` endpoint of the Authenticator.  Here is an example of the callback

    http://dev.localhost:3000/annotation/device_callback
        ?code  = GM730ri5HpYWA-Zo
        &state = 2N8hk9GC4mHg82RH8mex

Notice the `state` is common to all the URLs

**Authenticator confirms tokens**

The Authenticator will use the `code` and the secret `code_verifier` to get the Access token from Auth0

    # POST to 'https://dev-8821kz09.auth0.com/oauth/token'
     {
        "client_id": "FYlBPbNm7vZi9YPwVFyR7J2TLKrzNtST",
        "code": "F5yuOHbQL4Km-84T",
        "code_verifier": "9LscShb-3C2F-8PVsNaV_U9ArShyqTCzZWnUTT7IU54",
        "grant_type": "authorization_code",
        "redirect_uri": "http://dev.localhost:3000/annotation/device_callback"
    }

**Update Device Session**

The Authenticator can use the Access token to get ID token information, which is attached to the Device session.

**Device uses session**

Assuming the Device has not lost its session: The next time it makes a status call, it will be informed the session is verified.  Here is the response from the Authenticator: 
 

```
# Response from http://dev.localhost:3000/annotation/device_status
{
    "status": "verified",
    "try_again": false
}
```

At this point, the private RSA key on the Device client is not needed. The Device can then use the `requests.Session` object to make more requests from the API

```
# POST to http://dev.localhost:3000/annotation
{
    "from": "sample_data",
    "where": {"eq": {"revision12": "9e3ef2b6a889"}}
}
```
