# These are optional integrations. thinkingsdk imports them lazily at runtime via importlib,
# so excluding them here does not change behaviour: if the framework is installed in the
# environment the app actually runs in, the integration still loads. Excluding them stops
# PyInstaller from freezing an entire unused dependency tree into the bundle.
#
# This is not only about size. psycopg2 ships its own libssl, which shadowed the one CPython's
# _ssl module links against in a downstream bundle, breaking every HTTPS request in a shipped
# release. See issue #12.
#
# A consumer who genuinely wants this integration frozen in can re-add it with --hidden-import.
excludedimports = ['sqlalchemy']
