from setuptools import setup, find_packages

setup(
    name="scheduler",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "flask==3.0.0",
        "flask-cors==4.0.0",
        "sqlalchemy==2.0.23",
        "psycopg2-binary==2.9.9",
        "python-dotenv==1.0.0",
        "pydantic==2.5.0",
        "pydantic-settings==2.1.0",
        "ortools==9.8.3296",
        "scikit-learn==1.3.2",
        "numpy==1.24.3",
    ],
)