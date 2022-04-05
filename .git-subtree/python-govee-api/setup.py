import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

INSTALL_REQUIRES = [
    "aiohttp>=3.7.1",
    "bios>=0.1.2",
    "certifi>=2021.10.8",
    "dacite>=1.6.0",
    "events>=0.3",
    "pexpect>=4.8.0",
    "pygatt>=4.0.5",
    # , "govee_btled-1.0"
]

setuptools.setup(
    name="govee_api_laggat",
    version="0.2.2",
    author="Florian Lagg @LaggAt",
    author_email="florian.lagg@gmail.com",
    description="Implementation of the govee API to control LED strips and bulbs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LaggAt/python-govee-api",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    # dependency_links=['https://codeload.github.com/chvolkmann/govee_btled/tarball/master#egg=govee_btled-1.0'],
    install_requires=INSTALL_REQUIRES,
)
