#!/usr/bin/env python

import argparse
import logging
import subprocess
import nagiosplugin
import os

_log = logging.getLogger('nagiosplugin')


class ResticHealthCheck(nagiosplugin.Resource):

    def __init__(self, restic_bin='restic', repo=None,
                 password_file=None, sudo=False):
        self.restic_bin = restic_bin
        self.repo = repo
        self.password_file = password_file
        self.sudo = sudo
        self.stderr = None

    def probe(self):
        """
        Run restic and parse its return code

        :return:
        """

        # For some reason, check.main() is the only place where exceptions are
        # printed nicely
        if not self.repo and not os.environ.get('RESTIC_REPOSITORY'):
            raise nagiosplugin.CheckError(
                'Please specify repository location (-r, --repo or '
                '$RESTIC_REPOSITORY)')
        if not self.password_file and \
           not (os.environ.get('RESTIC_PASSWORD') or
                os.environ.get('RESTIC_PASSWORD_FILE')):
            raise nagiosplugin.CheckError(
                'Please specify password or its location (-p, --password-file,'
                ' $RESTIC_PASSWORD or $RESTIC_PASSWORD_FILE)')

        cmd = [self.restic_bin, 'check', '--quiet', '--no-lock']

        if self.sudo:
            cmd = ['sudo'] + cmd

        if self.repo:
            cmd.extend(['--repo', self.repo])
        if self.password_file:
            cmd.extend(['--password-file', self.password_file])

        _log.info('Using command: %s' % ' '.join(cmd))

        try:
            restic_result = subprocess.check_output(cmd,
                                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            yield nagiosplugin.Metric(self.repo, False, context='health_check')
            self.stderr = e.output.decode()
        except IOError as e:
            raise nagiosplugin.CheckError('Failed to run %s: %s' % (
                ' '.join(cmd), e))
        else:
            _log.debug('Got output: %s' % restic_result)
            yield nagiosplugin.Metric(self.repo, True, context='health_check')


class ResticHealthCheckContext(nagiosplugin.Context):
    def evaluate(self, metric, resource):
        if metric.value:
            return nagiosplugin.Ok
        return nagiosplugin.Critical

    def describe(self, metric):
        return metric.resource.stderr

class ResticSummary(nagiosplugin.Summary):
    def ok(self, results):
        """
        Show all results in the output

        :param results:
        :return:
        """
        ret = ['%s health check OK' % (r.metric.name) for r in results]
        return 'Repository %s' % ', '.join(ret)

    def problem(self, results):
        """
        Show only the results that have crossed the threshold

        :param results:
        :return:
        """
        ret = ['%s health check FAILED' % (r.metric.name) for r in results]
        return 'Repository %s failed' % ', '.join(ret)


@nagiosplugin.guarded
def main():
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument(
        '--sudo', action='store_true',
        help='Use "sudo" when invoking restic (default: %(default)s)')
    argp.add_argument(
        '--restic-bin', type=str, metavar='RESTIC-BIN', default='restic',
        help='Path to the restic binary, or the name of restic in $PATH '
             '(default: %(default)s)')
    argp.add_argument(
        '-r', '--repo', metavar='REPO',
        help='repository to check backups (default: $RESTIC_REPOSITORY)')
    argp.add_argument(
        '-p', '--password-file', metavar='PASSWORD_FILE',
        help='read the repository password from a file (default: '
             '$RESTIC_PASSWORD_FILE)')
    argp.add_argument('-v', '--verbose', action='count', default=0,
                      help='increase output verbosity (use up to 3 times)')
    argp.add_argument(
        '-t', '--timeout', metavar='SECONDS', type=int, default=60,
        help='Plugin timeout in seconds (default: %(default)s)')
    args = argp.parse_args()

    check = nagiosplugin.Check(
        ResticHealthCheck(restic_bin=args.restic_bin,
               repo=args.repo, password_file=args.password_file,
               sudo=args.sudo),
        ResticHealthCheckContext('health_check'),
        ResticSummary(),
        )

    check.main(verbose=args.verbose, timeout=args.timeout)


if __name__ == '__main__':
    main()
