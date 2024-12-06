from setuptools import setup, find_packages

setup(
    name='seamlessconv',
    version='0.0.1',
    author='Squirrel Modeller',
    author_email='seamlessconversation@gmail.com',
    description='A flexible and extensible framework for managing multi-agent conversations\
        with support for speech recognition, text-to-speech, and language model integration.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/Seamless-Conversation/seamless-conversation',
    packages=[f'seamlessconv.{p}' for p in find_packages(where='seamlessconv')],
    install_requires=open('requirements.txt').read().splitlines(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)
