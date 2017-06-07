from setuptools import setup, find_packages

dependencies = [
    'swsssdk>=2.0.1',
    'psutil>=4.0',
    'python_arptable>=0.0.1',
]

test_deps = [
    'mockredispy>=2.9.3',
    'pytest>=3.0.5',
]

high_performance_deps = [
    'swsssdk[high_perf]>=2.0.1',
]

setup(
    name='asyncsnmp',
    install_requires=dependencies,
    version='2.1.0',
    packages=find_packages('src'),
    extras_require={
        'testing': test_deps,
        'high_perf': high_performance_deps,
    },
    license='Apache 2.0',
    author='SONiC Team',
    author_email='linuxnetdev@microsoft.com',
    maintainer='Tom Booth',
    maintainer_email='thomasbo@microsoft.com',
    package_dir={'sonic_ax_impl': 'src/sonic_ax_impl',
                 'ax_interface': 'src/ax_interface'},
    package_data={'sonic_ax_impl': ['config/*.json',
                                    'bin/*',
                                    'systemd/*.service']},
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
    ],

)
