# Formaldehyde

A scaffolding script to convert a [Google Form](http://www.google.com/forms/about/) into a [bootstrapped](http://getbootstrap.com/) [Jekyll](http://jekyllrb.com/) sites with rough I18N support to run on GitHub Pages.

An example is the [Generation E](https://correctiv.github.io/generatione.eu/) ([GitHub repo](https://github.com/correctiv/generatione.eu)).


## Install

    bower install
    pip install -r requirements.txt

## Usage

    python formaldehyde.py <URL to HTML Google Form> <output folder> [optional template folder]

You can copy the template folder, modify it and then pass it as the third argument to use it for scaffolding.
