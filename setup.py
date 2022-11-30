long_description =  """\
The package *cypari* is a Python wrapper for the `PARI library
<http://pari.math.u-bordeaux.fr/>`_, a computer algebra system for
number theory computations.  It is derived from the `corresponding
component <https://github.com/sagemath/cypari2>`_
of `SageMath <http://www.sagemath.org>`_, but is independent of the rest of
SageMath and can be used with any recent version of Python 3.
"""

no_cython_message = """
You need to have Cython (>= 0.29) installed to build the CyPari
module since you're missing the autogenerated C/C++ files, e.g.

  sudo python -m pip install "cython>=0.29"

"""
import os, sys, re, sysconfig, subprocess, shutil, site, platform, time
try:
    assert sys.version_info.major == 3
except:
    print("Python 2 is not supported")
    sys.exit()
from glob import glob
from setuptools import setup, Command
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from distutils.command.sdist import sdist
from distutils.util import get_platform
from subprocess import Popen, PIPE

MSYS64_W = os.environ.get('MSYS64_DIR', r'C:\msys64')
MSYS64_U = os.environ.get('MSYS64_DIR', '/c/msys64')

if sys.version_info < (3,5):
    ('CyPari requires Python 3.5 or newer')
    sys.exit()

cpu_width = '64bit' if sys.maxsize > 2**32 else '32bit'

if sys.platform == 'win32':
    compiler_set = False
    ext_compiler = 'msvc'
    for n, arg in enumerate(sys.argv):
        if arg == '-c':
            ext_compiler = sys.argv[n+1]
            compiler_set = True
            break
        elif arg.startswith('-c'):
            ext_compiler = arg[2:]
            compiler_set = True
            break
        elif arg.startswith('--compiler'):
            ext_compiler = arg.split('=')[1]
            compiler_set = True
            break
    if not compiler_set and 'build' in sys.argv:
        sys.argv.append('--compiler=msvc')
else:
    ext_compiler = ''

# Path setup for building with the mingw C compiler on Windows.
if sys.platform == 'win32':
    # We always build the Pari library with mingw, no matter which compiler
    # is used for the CyPari extension.
    # Make sure that our C compiler matches our python and that we can run bash
    # and other needed utilities such as find.
    bash_proc = Popen(['bash', '-c', 'echo $PATH'], stdout=PIPE, stderr=PIPE)
    BASHPATH, _ = bash_proc.communicate()
    if cpu_width == '64bit':
        TOOLCHAIN_W = MSYS64_W + r'\ucrt64\bin'
        TOOLCHAIN_U = MSYS64_U + '/ucrt64/bin'
    else:
        TOOLCHAIN_W = MSYS64_W + r'\ucrt32\bin'
        TOOLCHAIN_U = MSYS64_U + '/ucrt32/bin'

    WINPATH=r'{0};{1}\bin;%{1}\usr\local\bin;{1}\usr\bin;'.format(
        TOOLCHAIN_W, MSYS64_W)
    BASHPATH='{0}:{1}'.format(TOOLCHAIN_U,BASHPATH.decode('utf-8'))
    KIT_PATH=r'/c/Program Files (x86)/Windows Kits/10/bin/10.0.22000.0/x64'
    BASH = r'%s\usr\bin\bash'%MSYS64_W
else:
    BASHPATH = os.environ['PATH']
    BASH = '/bin/bash'

if sys.platform == 'darwin':
    GMPDIR = 'gmp'
    PARIDIR = 'pari'
else:
    if cpu_width  == '64bit':
        GMPDIR = 'gmp64'
        PARIDIR = 'pari64'
    else:
        GMPDIR = 'gmp32'
        PARIDIR = 'pari32'

pari_include_dir = os.path.join('libcache', PARIDIR, 'include')
pari_library_dir = os.path.join('libcache', PARIDIR, 'lib')
pari_static_library = os.path.join(pari_library_dir, 'libpari.a')
gmp_library_dir = os.path.join('libcache', GMPDIR, 'lib')
gmp_static_library = os.path.join(gmp_library_dir, 'libgmp.a')

MSVC_include_dirs = [
    r'C:\Program Files (x86)\Windows Kits\10\Include\10.0.22000.0\um',
    r'C:\Program Files (x86)\Windows Kits\10\Include\10.0.22000.0\ucrt',
    r'C:\Program Files (x86)\Windows Kits\10\Include\10.0.22000.0\shared'
]

if cpu_width == '64bit':
    MSVC_extra_objects = [
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\um\x64\Uuid.lib',
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\um\x64\kernel32.lib',
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\ucrt\x64\ucrt.lib',
    ]
else:
    MSVC_extra_objects = [
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\um\x86\Uuid.lib',
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\um\x86\kernel32.lib',
    r'C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22000.0\ucrt\x86\ucrt.lib',
    os.path.abspath(os.path.join('Windows', 'gcc', 'libgcc.a')),
    ]
    
class CyPariClean(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        junkdirs = (glob('build/lib*') +
                    glob('build/bdist*') +
                    glob('build/temp*') +
                    glob('cypari*.egg-info')
        )
        for dir in junkdirs:
            try:
                shutil.rmtree(dir)
            except OSError:
                pass
        junkfiles = (glob('cypari/*.so*') +
                     glob('cypari/*.pyc') +
                     glob('cypari/_pari.c') +
                     glob('cypari/_pari*.h') +
                     glob('cypari/auto*.pxi') +
                     glob('cypari/auto*.pxd') +
                     glob('cypari/*.tmp')
        )
        for file in junkfiles:
            try:
                os.remove(file)
            except OSError:
                pass

class CyPariTest(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        minor = sys.version_info.minor
        major = sys.version_info.major
        dot = '' if minor > 10 else '.'
        platform = sysconfig.get_platform()
        platform += '-cpython' if minor > 10 else ''  
        build_lib_dir = os.path.join('build', f'lib.{platform}-{major}{dot}{minor}')
        sys.path.insert(0, os.path.abspath(build_lib_dir))
        from cypari.test import runtests
        sys.exit(runtests())

def check_call(args):
    try:
        subprocess.check_call(args)
    except subprocess.CalledProcessError:
        executable = args[0]
        command = [a for a in args if not a.startswith('-')][-1]
        raise RuntimeError(command + ' failed for ' + executable)

def python_major(python):
    proc = subprocess.Popen([python, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, errors = proc.communicate()
    # Python 2 writes to stderr, but Python 3 writes to stdout
    return (output + errors).decode().split()[1].split('.')[0]

class CyPariRelease(Command):
    user_options = [('install', 'i', 'install the release into each Python')]
    def initialize_options(self):
        self.install = False
    def finalize_options(self):
        pass
    def run(self):
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('dist'):
            shutil.rmtree('dist')
        os.remove('cypari/_pari.c')

        pythons = os.environ.get('RELEASE_PYTHONS', sys.executable).split(',')
        print('releasing for: %s'%(', '.join(pythons)))
        for python in pythons:
            check_call([python, 'setup.py', 'clean'])
            check_call([python, 'setup.py', 'build'])
            check_call([python, 'setup.py', 'test'])
            if sys.platform.startswith('linux'):
                plat = get_platform().replace('linux', 'manylinux1')
                plat = plat.replace('-', '_')
                check_call([python, 'setup.py', 'bdist_wheel', '-p', plat])
                check_call([python, 'setup.py', 'bdist_egg'])
            else:
                check_call([python, 'setup.py', 'bdist_wheel'])

            if self.install:
                check_call([python, 'setup.py', 'install'])

        # Build sdist using the *first* specified Python
        check_call([pythons[0], 'setup.py', 'sdist'])

        # Double-check the Linux wheels
        if sys.platform.startswith('linux'):
            for name in os.listdir('dist'):
                if name.endswith('.whl'):
                    subprocess.check_call(['auditwheel', 'repair',
                                           os.path.join('dist', name)])

win64_py3_decls = b'''
'''

win64_py2_decls = b'''
'''

decls = b'''
'''

class CyPariBuildExt(build_ext):

    def run(self):
        building_sdist = False

        if os.path.exists('pari_src'):
            # We are building an sdist.  Move the Pari source code into build.
            if not os.path.exists('build'):
                os.mkdir('build')
            os.rename('pari_src', os.path.join('build', 'pari_src'))
            os.rename('gmp_src', os.path.join('build', 'gmp_src'))
            building_sdist = True

        if (not os.path.exists(os.path.join('libcache', PARIDIR))
            or not os.path.exists(os.path.join('libcache', GMPDIR))):
            if sys.platform == 'win32':
                # This is meant to work even in a Windows Command Prompt
                if cpu_width == 64:
                    cmd = r'export PATH="%s" ; export MSYSTEM=MINGW64 ; bash build_pari.sh %s %s'%(
                        BASHPATH, PARIDIR, GMPDIR)
                else:
                    cmd = r'export PATH="%s" ; export MSYSTEM=MINGW32 ; bash build_pari.sh %s %s'%(
                        BASHPATH, PARIDIR, GMPDIR)
            else:
                cmd = r'export PATH="%s" ; bash build_pari.sh %s %s'%(BASHPATH, PARIDIR, GMPDIR)
            if subprocess.call([BASH, '-c', cmd]):
                sys.exit("***Failed to build PARI library***")

        if building_sdist:
            build_ext.run(self)
            return

        if (not os.path.exists(os.path.join('cypari', 'auto_gen.pxi')) or
            not os.path.exists(os.path.join('cypari', 'auto_instance.pxi'))):
            import autogen
            autogen.rebuild()

        # Provide declarations in an included .pxi file which indicate
        # whether we are building for 64 bit Python on Windows, and
        # which version of Python we are using.  We need to handle 64
        # bit Windows differently because (a) it is the only 64 bit
        # system with 32 bit longs and (b) Pari deals with this by:
        # #define long long long thereby breaking lots of stuff in the
        # Python headers.
        long_include = os.path.join('cypari', 'pari_long.pxi')
        if sys.platform == 'win32' and cpu_width == '64bit':
            if sys.version_info.major == 2:
                include_file = os.path.join('cypari', 'long_win64py2.pxi')
            else:
                include_file = os.path.join('cypari', 'long_win64py3.pxi')
        else:
            include_file = os.path.join('cypari', 'long_generic.pxi')
        with open(include_file, 'rb') as input:
            code = input.read()
        # Don't touch the long_include file unless it has changed, to avoid
        # unnecessary compilation.
        if os.path.exists(long_include):
            with open(long_include, 'rb') as input:
                old_code = input.read()
        else:
            old_code = b''
        if old_code != code:
            with open(long_include, 'wb') as output:
                output.write(code)

        # If we have Cython, check that .c files are up to date
        try:
            from Cython.Build import cythonize
            cythonize([os.path.join('cypari', '_pari.pyx')],
                      compiler_directives = {'language_level':3})
        except ImportError:
            if not os.path.exists(os.path.join('cypari', '_pari.c')):
                sys.exit(no_cython_message)

        build_ext.run(self)

class CyPariSourceDist(sdist):

    def _tarball_info(self, lib):
        lib_re = re.compile('(%s-[0-9\.]+)\.tar\.[bg]z2*'%lib)
        for f in os.listdir('.'):
            lib_match = lib_re.search(f)
            if lib_match:
                break
        return lib_match.group(), lib_match.groups()[0]

    def run(self):
        tarball, dir = self._tarball_info('pari')
        check_call(['tar', 'xfz', tarball])
        os.rename(dir, 'pari_src')
        tarball, dir = self._tarball_info('gmp')
        check_call(['tar', 'xfj', tarball])
        os.rename(dir, 'gmp_src')
        sdist.run(self)
        shutil.rmtree('pari_src')
        shutil.rmtree('gmp_src')

link_args = []
if sys.platform == 'darwin':
    compile_args=['-mmacosx-version-min=10.9']
else:
    compile_args = []
if ext_compiler == 'mingw32':
    major, minor = sys.version_info.major, sys.version_info.minor
    if major == 3:
        if minor == 4:
            link_args = [r'C:\Windows\System32\Python34.dll']
            link_args += ['-specs=specs100']
    else:
        link_args = ['-specs=specs90']
    link_args += ['-Wl,--subsystem,windows']
    compile_args += ['-D__USE_MINGW_ANSI_STDIO',
                     '-Dprintf=__MINGW_PRINTF_FORMAT']
    if cpu_width == '64bit':
        compile_args.append('-DMS_WIN64')
elif ext_compiler == 'msvc':
    # Ignore the assembly language inlines when building the extension.
    compile_args += ['/DDISABLE_INLINE']
    if False:  # Toggle for debugging symbols
        compile_args += ['/Zi']
        link_args += ['/DEBUG']
    # Add the mingw crt objects needed by libpari.
    if cpu_width == '64bit':
         link_args += [
             os.path.join('Windows', 'crt', 'libparicrt64.a'),
             'legacy_stdio_definitions.lib',
             os.path.join('Windows', 'crt', 'get_output_format64.o'),
         ]
    else:
         link_args += [
             os.path.join('Windows', 'crt', 'libparicrt32.a'),
             'legacy_stdio_definitions.lib',
             os.path.join('Windows', 'crt', 'get_output_format32.o')
         ]

link_args += [pari_static_library, gmp_static_library]

if sys.platform.startswith('linux'):
    link_args += ['-Wl,-Bsymbolic-functions', '-Wl,-Bsymbolic']

include_dirs = [pari_include_dir]
extra_objects = []
if sys.platform == 'win32':
    include_dirs += MSVC_include_dirs
    extra_objects += MSVC_extra_objects

_pari = Extension(name='cypari._pari',
                     sources=['cypari/_pari.c'],
                     include_dirs=include_dirs,
                     extra_objects=extra_objects,
                     extra_link_args=link_args,
                     extra_compile_args=compile_args)

# Load the version number.
sys.path.insert(0, 'cypari')
from version import __version__
sys.path.pop(0)

setup(
    name = 'cypari',
    version = __version__,
    description = "Sage's PARI extension, modified to stand alone.",
    packages = ['cypari'],
    package_dir = {'cypari':'cypari'},
    cmdclass = {
        'build_ext': CyPariBuildExt,
        'clean': CyPariClean,
        'test': CyPariTest,
        'release': CyPariRelease,
        'sdist': CyPariSourceDist,
    },
    ext_modules = [_pari],
    zip_safe = False,
    long_description = long_description,
    url = 'https://github.com/3-manifolds/cypari',
    author = 'Marc Culler and Nathan M. Dunfield',
    author_email = 'culler@uic.edu, nathan@dunfield.info',
    license='GPLv2+',
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: C',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Mathematics',
        ],
    keywords = 'Pari, SageMath, SnapPy',
)
