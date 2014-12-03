import sys
import os
import errno
import shutil

from lxml import etree
import yaml
import requests
from jinja2 import Template


def write_yaml(obj):
    return yaml.safe_dump(obj, allow_unicode=True,
        default_flow_style=False, encoding='utf-8', width=10000)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def get_docs_key(url):
    return url.split('/')[-2]


class GoogleFormParser(object):
    def __init__(self, root):
        self.root = root

    def get_questions(self):
        questions = self.root.xpath('//*[contains(@class, "ss-form-question")]')
        for qnum, question in enumerate(questions, 1):
            question_item = question.xpath('./*[contains(@class, "ss-item")]')[0]
            label = question_item.xpath('.//*[contains(@class, "ss-q-title")]')[0].text.strip()
            q = {
                'label': label,
                'question_number': qnum,
                'qtype': 'unknown',
                'required': 'ss-item-required' in question_item.attrib['class']
            }
            klass = question_item.attrib['class']
            if 'ss-radio' in klass:
                q.update(self.get_radio(question_item))
            elif 'ss-text' in klass:
                q.update(self.get_text(question_item))
            elif 'ss-paragraph-text' in klass:
                q.update(self.get_paragraph_text(question_item))
            elif 'ss-checkbox' in klass:
                q.update(self.get_checkbox(question_item))
            elif 'ss-select' in klass:
                q.update(self.get_select(question_item))
            else:
                q.update({'name': 'none', 'label': 'label'})
            yield q

    def get_radio(self, item):
        choices = item.xpath('.//input[@type="radio"]')
        choice_other = item.xpath('.//input[@value="__other_option__"]')
        return {
            'qtype': 'radio',
            'name': choices[0].attrib['name'],
            'choices': [{'label': c.attrib['value'], 'value': c.attrib['value']}
                for c in choices],
            'choice_other': bool(choice_other)
        }

    def get_select(self, item):
        select = item.xpath('.//select')[0]
        options = select.xpath('./option')
        return {
            'qtype': 'select',
            'name': select.attrib['name'],
            'choices': [{'label': c.text, 'value': c.attrib['value']}
                for c in options if c.attrib['value']]
        }

    def get_checkbox(self, item):
        choices = item.xpath('.//input[@type="checkbox"]')
        choice_other = item.xpath('.//input[@value="__other_option__"]')
        return {
            'qtype': 'checkbox',
            'name': choices[0].attrib['name'],
            'choices': [{'label': c.attrib['value'], 'value': c.attrib['value']}
                for c in choices],
            'choice_other': bool(choice_other)
        }

    def get_text(self, item):
        text = item.xpath('.//input')[0]
        return {
            'qtype': 'text',
            'name': text.attrib['name'],
            'label': text.attrib['aria-label'].strip(),
            'type': text.attrib['type']
        }

    def get_paragraph_text(self, item):
        text = item.xpath('.//textarea')[0]
        return {
            'qtype': 'paragraph-text',
            'name': text.attrib['name'],
            'label': text.attrib['aria-label'].strip()
        }


class Formaldehyde(object):
    def __init__(self, output_path=None, template_path=None, language='en',
                       encoding='utf-8'):
        self.output_path = output_path
        if template_path is None:
            self.template_path = os.path.join(os.path.dirname(
                    os.path.abspath(__file__)), 'template')
        self.language = language
        self.encoding = encoding

    def generate(self, url):
        self.key = get_docs_key(url)
        response = requests.get(url)
        self.generate_from_string(response.text)

    def generate_from_string(self, content):
        parser = etree.HTMLParser()
        root = etree.fromstring(content, parser=parser)
        form_parser = GoogleFormParser(root)
        questions = list(form_parser.get_questions())
        self.scaffold(questions)

    def write_language_template(self, name, content):
        file_path = os.path.join(self.output_path, self.language, name)
        mkdir_p(os.path.dirname(file_path))
        with open(file_path, 'w') as f:
            f.write(content.encode(self.encoding))

    def copy_template(self, name, tree=False):
        from_path = os.path.join(self.template_path, name)
        to_path = os.path.join(self.output_path, name)
        if tree:
            shutil.rmtree(to_path)
            shutil.copytree(from_path, to_path)
        else:
            shutil.copy(from_path, to_path)

    def scaffold(self, questions):
        outdir = self.output_path
        # _data/config.yml
        self.render_file('_config.yml', {
            'key': self.key
        })

        self.render_file('lang/index.html', {'language': self.language},
                        os.path.join(self.language, 'index.html'))
        self.render_file('lang/thanks.html', {'language': self.language},
                        os.path.join(self.language, 'thanks', 'index.html'))
        self.render_file('lang/about.html', {'language': self.language},
                        os.path.join(self.language, 'about', 'index.html'))

        self.copy_template('Gemfile')
        self.copy_template('index.html')
        self.copy_template('_layouts/base.html')
        self.copy_template('_layouts/default.html')
        self.copy_template('_layouts/page.html')
        self.copy_template('static', tree=True)

        # _data/questions.yml
        q_yaml_path = os.path.join(outdir, '_data', 'questions.yml')
        mkdir_p(os.path.dirname(q_yaml_path))
        q_data = {
            'meta': {
                'q_%d' % i: {
                    'name': q['name'],
                    'label': q['label'],
                    'required': q['required']
                } for i, q in enumerate(questions, 1)
            },
            self.language: {'q_%d' % i: self.yamlify_question(q) for i, q in enumerate(questions, 1)}
        }

        q_yaml = write_yaml(q_data)
        open(q_yaml_path, 'w').write(q_yaml)

        self.scaffold_form(questions)

    def yamlify_question(self, question):
        data = {
            'label': question['label'].strip()
        }

        if 'choices' in question:
            data.update({
                'choices': question['choices'],
                'choice_other': question.get('choice_other', False)
            })

        return data

    def _get_template(self, *names):
        for name in names:
            path = os.path.join(self.template_path, name)
            if not os.path.exists(path):
                continue
            return Template(open(path).read().decode(self.encoding))
        return Template('')

    def render_file(self, path, context, output_path=None):
        template = self._get_template(path)
        if output_path is None:
            output_path = path
        file_path = os.path.join(self.output_path, output_path)
        mkdir_p(os.path.dirname(file_path))
        with open(file_path, 'w') as fileobj:
            fileobj.write(template.render(**context).encode(self.encoding))

    def scaffold_form(self, questions):
        form_path = os.path.join(self.output_path, '_layouts', 'form.html')
        mkdir_p(os.path.dirname(form_path))

        context = {
            'questions': questions,
            'language': self.language
        }

        with open(form_path, 'w') as form_file:

            template = self._get_template('form/form_head.html')
            form_file.write(template.render(**context).encode(self.encoding))
            form_file.write('\n\n')

            for i, q in enumerate(context['questions'], 1):
                context['question'] = q
                template = self._get_template('form/field_head.html')
                form_file.write(template.render(**context).encode(self.encoding))
                template = self._get_template(
                    'form/q_%d.html' % i,
                    'form/form_%s.html' % q['qtype']
                )
                form_file.write(template.render(**context).encode(self.encoding))
                form_file.write('\n\n')

            template = self._get_template('form/form_tail.html')
            form_file.write(template.render(**context).encode(self.encoding))


def main(url, output_path, template_path=None):
    fh = Formaldehyde(output_path, template_path=template_path)
    fh.generate(url)


if __name__ == '__main__':
    main(*sys.argv[1:])
