import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

INSTALL_REQUIRES = [
    "aiohttp[speedups]>=3.7.1", 
    "events>=0.3",
    "pygatt>=4.0.5",
    "pexpect>=4.8.0",
    #, "govee_btled-1.0"
]

setuptools.setup(
    name="govee_api_laggat",
    version="0.1.40",
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
