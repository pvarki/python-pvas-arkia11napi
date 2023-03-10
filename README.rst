===========
arkia11napi
===========

FastAPI for PVARKI user management, authentication and authorization


Configuration
-------------

You need to configure some things even when running the development server locally since we do not want
to default into signing JWTs with the insecure test keys.

See dotenv.example on what you need to put into your .env -file.

Mailhog
^^^^^^^

Example dotenv is configured for MailHog to be used with development::

    docker run -d -p 8025:8025 -p 1025:1025 mailhog/mailhog

go to http://localhost:8025/ to view the emails.

Docker
------

For more controlled deployments and to get rid of "works on my computer" -syndrome, we always
make sure our software works under docker.

It's also a quick way to get started with a standard development environment::

    docker-compose -p a11napi -f docker-compose_local.yml -f docker-compose_local_reload.yml up

Then go to http://localhost:8100/api/docs and http://localhost:8125/


SSH agent forwarding
^^^^^^^^^^^^^^^^^^^^

We need buildkit_::

    export DOCKER_BUILDKIT=1

.. _buildkit: https://docs.docker.com/develop/develop-images/build_enhancements/

And also the exact way for forwarding agent to running instance is different on OSX::

    export DOCKER_SSHAGENT="-v /run/host-services/ssh-auth.sock:/run/host-services/ssh-auth.sock -e SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock"

and Linux::

    export DOCKER_SSHAGENT="-v $SSH_AUTH_SOCK:$SSH_AUTH_SOCK -e SSH_AUTH_SOCK"

Creating a development container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Build image, create container and start it::

    docker build --ssh default --target devel_shell -t arkia11napi:devel_shell .
    docker create --name arkia11napi_devel -v `pwd`":/app" -it `echo $DOCKER_SSHAGENT` arkia11napi:devel_shell
    docker start -i arkia11napi_devel

Though you will also need database & mailhog so it might be better to fire up this composition::

    docker-compose -f docker-compose_local.yml -f docker-compose_local_reload.yml up

You can then get a shell with::

    docker-compose -f docker-compose_local.yml -f docker-compose_local_reload.yml exec -it api /bin/zsh -l

To initialize superadmin role and user with that role in the shell run::

    arkia11napi init-admin testuser@example.com


pre-commit considerations
^^^^^^^^^^^^^^^^^^^^^^^^^

If working in Docker instead of native env you need to run the pre-commit checks in docker too::

    docker exec -i arkia11napi_devel /bin/bash -c "pre-commit install"
    docker exec -i arkia11napi_devel /bin/bash -c "pre-commit run --all-files"

You need to have the container running, see above. Or alternatively use the docker run syntax but using
the running container is faster::

    docker run --rm -it -v `pwd`":/app" arkia11napi:devel_shell -c "pre-commit run --all-files"

Test suite
^^^^^^^^^^

You can use the devel shell to run py.test when doing development, for CI use
the "tox" target in the Dockerfile::

    docker build --ssh default --target tox -t arkia11napi:tox .
    docker run --rm -it -v `pwd`":/app" `echo $DOCKER_SSHAGENT` --net host -v /var/run/docker.sock:/var/run/docker.sock arkia11napi:tox

Production docker
^^^^^^^^^^^^^^^^^

There's a "production" target as well for running the application, remember to change that
architecture tag to arm64 if building on ARM::

    docker build --ssh default --target production -t arkia11napi:amd64-latest .
    docker run -it --name arkia11napi arkia11napi:amd64-latest

Development
-----------

TLDR:

- Create and activate a Python 3.8 virtualenv (assuming virtualenvwrapper)::

    mkvirtualenv -p `which python3.8` my_virtualenv

- change to a branch::

    git checkout -b my_branch

- install Poetry: https://python-poetry.org/docs/#installation
- Install project deps and pre-commit hooks::

    poetry install
    pre-commit install
    pre-commit run --all-files

- Ready to go.

Remember to activate your virtualenv whenever working on the repo, this is needed
because pylint and mypy pre-commit hooks use the "system" python for now (because reasons).
