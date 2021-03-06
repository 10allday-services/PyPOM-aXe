# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


import json
import os
import time
import re

_DEFAULT_SCRIPT = os.path.join(os.path.dirname(__file__), 'src', 'axe.min.js')


def inject(page):
    """
    Recursively inject aXe into all iframes and the top level document.

    :param script_url: location of the axe-core script.
    :type script_url: string
    """
    with open(_DEFAULT_SCRIPT) as f:
        page.selenium.execute_script(f.read())

def execute(page, context=None, options=None):
    """
    Run axe against the current page.

    :param context: which part of the page to analyze.
    :param options: dictionary of aXe options.
    """
    template = 'return axe.run(%s).then(function(result){return result;});'
    args = ''

    # If context parameter is passed, add to args
    if context is not None:
        args += '%r' % context
    # Add comma delimiter only if both parameters are passed
    if context is not None and options is not None:
        args += ','
    # If options parameter is passed, add to args
    if options is not None:
        args += '%s' % options

    command = template % args
    response = page.selenium.execute_script(command)
    return response

def impact_included(rule, impact):
    """Filter violations with specified impact level or higher."""
    if impact == 'minor' or impact is None:
        return True
    elif impact == 'serious':
        if rule['impact'] != 'minor':
            return True
    elif impact == 'critical':
        if rule['impact'] == 'critical':
            return True
    else:
        return False

def run(page, context=None, options=None, impact=None):
    """Inject aXe, run against current page, and return rules & violations."""
    inject(page)
    data = execute(page, context, options)
    violations = dict((rule['id'], rule) for rule in data['violations']
                      if impact_included(rule, impact))
    return violations

def pypom_after_wait_for_page_to_load(page, context=None, options=None, impact=None):
    """Run aXe accessibility checks, and write results to file."""
    # Run accessibility tests only if not disabled.
    disable_a11y = os.environ.get('ACCESSIBILITY_DISABLED')
    if disable_a11y == 'false' or disable_a11y == None:
        violations = run(page, context, options, impact)
        print(violations)
        # Output results only if reporting is enabled.
        if os.environ.get('ACCESSIBILITY_REPORTING') == 'true':
            # Format file name based on page title and current datetime.
            t = time.strftime("%m_%d_%Y_%H:%M:%S")
            title = page.selenium.title
            title = re.sub('[\s\W]', '-', title)
            title = re.sub('(-|_)+', '-', title)

            # Write JSON results to file
            write_results('results/%s_%s.json' % (title, t), violations)
        assert len(violations) == 0, report(violations)

def report(violations):
    """Format output of accessibility violations."""
    string = ''
    string += 'Found ' + str(len(violations)) + ' accessibility violations:'
    for violation, rule in violations.items():
        string += '\n\n\nRule Violated:\n' + rule['id'] + ' - ' + rule['description'] + \
            '\n\tURL: ' + rule['helpUrl'] + \
            '\n\tImpact Level: ' + rule['impact'] + \
            '\n\tTags:'
        for tag in rule['tags']:
            string += ' ' + tag
        string += '\n\tElements Affected:'
        i = 1
        for node in rule['nodes']:
            for target in node['target']:
                string += '\n\t' + str(i) + ') Target: ' + target
                i += 1
            for item in node['all']:
                string += '\n\t\t' + item['message']
            for item in node['any']:
                string += '\n\t\t' + item['message']
            for item in node['none']:
                string += '\n\t\t' + item['message']
        string += '\n\n\n'

    return string

def write_results(name, output):
    """
    Write JSON to file with the specified name.

    :param name: Name of file to be written to.
    :param output: JSON object.
    """
    with open(name, 'w+') as f:
        f.write(json.dumps(output, indent=4))
