import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

INSTALL_REQUIRES = [
    "aiohttp", "aiohttp[speedups]"
]

setuptools.setup(
    name="govee_api_laggat",
    version="0.1.21",
    author="Florian Lagg @LaggAt",
    author_email="florian.lagg@gmail.com",
    description="Implementation of the govee API to control LED strips and bulbs.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LaggAt/govee-api-laggat",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=INSTALL_REQUIRES
)