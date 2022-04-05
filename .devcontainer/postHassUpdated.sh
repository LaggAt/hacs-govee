
/bin/echo ------------ postCreateCommand downgrade pip packages with breaking changes ------------
## downgrade jinja2 as they dropped contextfilter and current home assistant needs this: https://jinja.palletsprojects.com/en/3.0.x/changes/
## also downgrade markupsafe for dropped soft_unicode: https://markupsafe.palletsprojects.com/en/2.1.x/changes/#version-2-1-0
pip install --upgrade jinja2==2.11.3 markupsafe==2.0.1

/bin/echo ------------ postCreateCommand symlink our component ------------
/bin/mkdir -p /config/custom_components
/bin/ln -s /workspaces/hacs-govee/custom_components/govee /config/custom_components/govee

/bin/echo ------------ postCreateCommand container install ------------
pip install -e /workspaces/hacs-govee/.git-subtree/python-govee-api/

/bin/echo ------------ postCreateCommand python/pip ------------
/usr/local/bin/python3 -m pip install --upgrade pip
/usr/local/bin/pip3 install black colorlog debugpy pexpect pygatt pylint PyNaCl==1.3.0
/usr/local/bin/pip3 install -r /workspaces/hacs-govee/requirements_test.txt

/bin/echo ------------ postCreateCommand install hacs ------------
mkdir -p /src/hacs
cd /src/hacs
/bin/mkdir -p /config/custom_components/hacs
/usr/bin/wget -c https://github.com/hacs/integration/releases/latest/download/hacs.zip
/usr/bin/unzip -o hacs.zip -d /config/custom_components/hacs
/bin/rm hacs.zip

