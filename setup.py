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
    'fabric==0.9.3'
]


setup(name='.',
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
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
)
