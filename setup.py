from setuptools import setup, find_packages
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()


version = '0.1'

install_requires = [
    'celery==2.2',
    'jinja2',
    'nose',
    'fabric==0.9.3',
    'sqlalchemy',
]


setup(name='dz_tasks',
    version=version,
    description="NodeRabbit tasks for RabbitMQ!",
    long_description=README + '\n\n' + NEWS,
    classifiers=[
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='',
    author='Node Rabbit',
    author_email='all@noderabbit.com',
    url='http://noderabbit.com',
    license='Proprietary',
    namespace_packages=["dz"],
    packages=find_packages('.'),
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
)
