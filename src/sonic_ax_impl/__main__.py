import logging.handlers
import os
import shutil
import sys

import sswsdk.util

import ax_interface
import sonic_ax_impl

LOG_FORMAT = "snmp-subagent [%(name)s] %(levelname)s: %(message)s"


def install_file(src_filename, dest_dir, executable=False):
    dest_file = shutil.copy(src_filename, dest_dir)
    print("copied: ", dest_file)
    if executable:
        print("chmod +x {}".format(dest_file))
        st = os.stat(dest_file)
        os.chmod(dest_file, st.st_mode | 0o111)


def install_fragments():
    local_filepath = os.path.dirname(os.path.abspath(__file__))
    pass_script = os.path.join(local_filepath, 'bin/sysDescr_pass.py')
    install_file(pass_script, '/usr/share/snmp', executable=True)


if __name__ == "__main__":

    if 'install' in sys.argv:
        install_fragments()
        sys.exit(0)

    # import command line arguments
    args = sswsdk.util.process_options("sonic_ax_impl")

    # configure logging. If debug '-d' is specified, logs to stdout at designated level. syslog/INFO otherwise.
    log_level = log_level_sdk = args.get('log_level')
    warn_syslog = False
    if log_level is None:
        try:
            logging_handler = logging.handlers.SysLogHandler(address='/dev/log',
                                                             facility=logging.handlers.SysLogHandler.LOG_DAEMON)
        except (AttributeError, OSError):
            # when syslog is unavailable, log to stderr
            logging_handler = logging.StreamHandler(sys.stderr)
            warn_syslog = True

        logging_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        sonic_ax_impl.logger.addHandler(logging_handler)
        log_level = logging.INFO
        log_level_sdk = logging.ERROR
    else:
        sonic_ax_impl.logger.addHandler(logging.StreamHandler(sys.stdout))

    # set the log levels
    sonic_ax_impl.logger.setLevel(log_level)
    ax_interface.logger.setLevel(log_level)
    sswsdk.logger.setLevel(log_level_sdk)

    # inherit logging handlers in submodules
    ax_interface.logger.handlers = sonic_ax_impl.logger.handlers
    sswsdk.logger.handlers = sonic_ax_impl.logger.handlers

    if warn_syslog:
        # syslog was unavailable when it should've been.
        sonic_ax_impl.logger.warning("Syslog is unavailable. Logging to STDERR.")

    from .main import main

    main(update_frequency=args.get('update_frequency'))
