from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/curp')
def curp_entry():
    return render_template('curp_entry.html')


@app.route('/lifesim')
def lifesim_entry():
    return render_template('lifesim_entry.html')


@app.route('/coming-soon/<feature_key>')
def coming_soon(feature_key: str):
    feature_map = {
        'interview-modeling': '以访谈的形式进行深度的个体建模',
        'marketing-test': '营销方法的用户测试',
    }
    return render_template('coming_soon.html', feature_name=feature_map.get(feature_key, '功能建设中'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
