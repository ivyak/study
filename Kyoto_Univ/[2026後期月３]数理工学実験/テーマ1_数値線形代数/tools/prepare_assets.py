"""既存図・CSV・追加実験から、レポート用の図と集計を生成する。"""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SECTION = ROOT.parent / 'section2'
NS = {'s': 'http://www.w3.org/2000/svg'}


def recover_svg(path):
    # MatplotlibのSVG座標と目盛の対応から可視点を復元する。
    root = ET.fromstring(path.read_text(), parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    ticks = []
    for group in root.findall('.//s:g', NS):
        if not group.get('id', '').startswith('ytick_'): continue
        comments = ' '.join(e.text or '' for e in group.iter() if e.tag is ET.Comment)
        match = re.search(r'(?:(\d+(?:\.\d+)?)\\+times)?10\^\{(-?\d+)\}', comments)
        if not match: continue
        mark = group.find('.//s:use', NS)
        ticks.append((float(mark.get('y')), np.log10(float(match[1] or 1)) + float(match[2])))
    assert len(ticks) >= 2, path
    coef = np.polyfit(*np.array(ticks).T, 1)
    groups = [g for g in root.findall('.//s:g', NS)
              if g.get('id', '').startswith('line2d_') and len(g.findall('.//s:use', NS)) >= 90]
    assert len(groups) == 1, (path, len(groups))
    marks = groups[0].findall('.//s:use', NS)
    assert len(marks) == 100, (path, len(marks))
    return [float(10 ** np.polyval(coef, float(mark.get('y')))) for mark in marks]


def new_plots(csv_name, task):
    rows = list(csv.DictReader((ROOT / 'data' / csv_name).open()))
    methods = list(dict.fromkeys(r['method'] for r in rows))
    metrics = [key for key in ['residual', 'error', 'eigenvalue_error', 'eigenvector_error', 'time', 'iterations'] if key in rows[0]]
    labels = {'residual':'Residual norm', 'error':'Relative error', 'eigenvalue_error':'Relative eigenvalue error', 'eigenvector_error':'Relative eigenvector error', 'time':'Execution time (s)', 'iterations':'Iterations'}
    ylabels = [labels[key] for key in metrics]
    sizes = list(dict.fromkeys(int(r['n']) for r in rows))
    if len(sizes) == 1:
        fig, axes = plt.subplots(3, 2, figsize=(6.8, 8.6))
        for index, (ax, metric, ylabel) in enumerate(zip(axes.flat, metrics, ylabels)):
            for name in methods:
                selected = [r for r in rows if r['method'] == name]
                ax.plot([int(r['trial']) for r in selected], [float(r[metric]) for r in selected], '.', markersize=3, label=name)
            ax.set(title=f'({chr(97+index)}) n = {sizes[0]}', xlabel='Trial', ylabel=ylabel)
            ax.tick_params(labelsize=8)
            if metric != 'iterations': ax.set_yscale('log')
            ax.grid(True, which='both', alpha=.35)
            ax.legend()
        axes.flat[-1].axis('off')
        fig.tight_layout()
        fig.savefig(ROOT / f'figures/{task}_comparison.pdf')
        plt.close(fig)
        return
    for metric, ylabel in zip(metrics, ylabels):
        sizes = list(dict.fromkeys(int(r['n']) for r in rows))
        if len(sizes) == 4:
            fig, axes = plt.subplots(2, 2, figsize=(6.8, 5.7))
            axes = axes.flat
        else:
            fig, ax = plt.subplots(figsize=(6.4, 4.8))
            axes = [ax]
        for ax, n in zip(axes, sizes):
            for name in methods:
                selected = [r for r in rows if int(r['n']) == n and r['method'] == name]
                ax.plot([int(r['trial']) for r in selected], [float(r[metric]) for r in selected], '.', markersize=3, label=name)
            ax.set(title=f'n = {n}', xlabel='Trial', ylabel=ylabel)
            ax.tick_params(labelsize=8)
            if metric != 'iterations': ax.set_yscale('log')
            ax.grid(True, which='both', alpha=.35)
            if len(methods)>1: ax.legend()
        fig.tight_layout()
        fig.savefig(ROOT / f'figures/{task}_{metric}.pdf')
        plt.close(fig)


def summarize(rows, metrics):
    groups = defaultdict(list)
    for row in rows: groups[(int(row['n']), row['method'])].append(row)
    result=[]
    for (n, method), group in groups.items():
        good=[r for r in group if np.isfinite(float(r['time']))]
        record={'n': n, 'method': method, 'total': len(group), 'success': len(good)}
        for key in metrics:
            a=np.array([float(r[key]) for r in good])
            record[key]={'median': float(np.median(a)), 'min': float(a.min()), 'max': float(a.max())} if len(a) else None
        result.append(record)
    return result



def tex_number(value):
    if value is None or not np.isfinite(value): return '--'
    if value == 0: return '$0$'
    if 0.001 <= abs(value) < 10000: return f'${value:.3g}$'
    mantissa, exponent = f'{value:.2e}'.split('e')
    return rf'${mantissa}\times10^{{{int(exponent)}}}$'


def write_tables(summary):
    definitions=[]
    def table(command, headers, rows, align):
        body=' & '.join(headers)+r'\\\midrule'+'\n'
        body+='\n'.join(' & '.join(row)+r'\\' for row in rows)
        definitions.append('\\newcommand{\\'+command+r'}{\begin{tabular}{'+align+r'}\toprule '+body+r'\bottomrule\end{tabular}}')
    for method, command in [('Gaussian','LinearGaussian'),('LU','LinearLU')]:
        data=[r for r in summary['legacy_linear'] if r['method']==method]
        table(command, ['$n$','残差','相対誤差','時間 / s'],
              [[str(r['n'])]+[tex_number(r[k]['median']) for k in ['residual','error','time']] for r in data], 'rrrr')
    names={'Gaussian':'消去法','LU':'LU法','Power method':'べき乗法','Power + inverse':'組合せ法','QR':'通常法','Original QR':'通常法','Shift + Deflation':'改良法'}
    table('PairedSummary', ['$n$','手法','残差','相対誤差','時間 / s'],
          [[str(r['n']), names[r['method']]]+[tex_number(r[k]['median']) for k in ['residual','error','time']] for r in sorted(summary['paired'],key=lambda r:(r['n'],r['method']))], 'rlrrr')
    table('PowerSummary', ['$n$','残差','固有値誤差','ベクトル誤差','時間 / s','回数'],
          [[str(r['n'])]+[(f"${r[k]['median']:g}$" if k=='iterations' else tex_number(r[k]['median'])) for k in ['residual','eigenvalue_error','eigenvector_error','time','iterations']] for r in summary['power']], 'rrrrrr')
    table('SpectralSummary', ['$n$','比の中央値'],
          [[str(r['n']),tex_number(r['spectral_ratio']['median'])] for r in summary['power']], 'rr')
    table('InverseSummary', ['手法','残差','固有値誤差','ベクトル誤差','時間 / s','回数'],
          [[names[r['method']]]+[(f"${r[k]['median']:g}$" if k=='iterations' else tex_number(r[k]['median'])) for k in ['residual','eigenvalue_error','eigenvector_error','time','iterations']] for r in summary['power_inverse']], 'lrrrrr')
    table('QRSummary', ['$n$','成功数','最大残差','最大相対誤差','時間 / s','回数'],
          [[str(r['n']),f"{r['success']}/100"]+[(f"${r[k]['median']:g}$" if k=='iterations' else tex_number(r[k]['median'])) for k in ['residual','error','time','iterations']] for r in summary['qr6_1']], 'rrrrrr')
    table('ShiftSummary', ['$n$','手法','成功数','最大残差','最大相対誤差','時間 / s','回数'],
          [[str(r['n']),names[r['method']],f"{r['success']}/100"]+[(f"${r[k]['median']:g}$" if k=='iterations' else tex_number(r[k]['median'])) for k in ['residual','error','time','iterations']] for r in summary['qr7']], 'rlrrrrr')
    table('ShiftSpeedSummary', ['$n$','対の数','時間比の中央値'],
          [[str(r['n']),str(r['pairs']),tex_number(r['median_ratio'])] for r in summary['qr_paired_speedup']], 'rrr')
    (ROOT/'tables.tex').write_text('\n\n'.join(definitions)+'\n')

def main():
    for name in ['figures', 'data']: (ROOT/name).mkdir(exist_ok=True)
    legacy=[]
    plt.rcParams.update({'font.size':9, 'axes.titlesize':10, 'axes.labelsize':9, 'legend.fontsize':8})
    for task in ['1_1','2_1']:
        for n in [100,200,400,800]:
            values={metric: recover_svg(SECTION/f'figures/kadai{task}_n{n}_{metric}.svg') for metric in ['residual','error','time']}
            for i in range(100): legacy.append({'n': n, 'trial': i+1, 'method': 'Gaussian' if task=='1_1' else 'LU', **{metric: v[i] for metric,v in values.items()}})
    summary={'legacy_linear': summarize(legacy,['residual','error','time'])}
    for method, task in [('Gaussian','kadai1_1'),('LU','kadai2_1')]:
        path=ROOT/f'data/{task}_from_svg.csv'
        with path.open('w', newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['n','trial','method','residual','error','time']); writer.writeheader(); writer.writerows(r for r in legacy if r['method']==method)
        new_plots(path.name,task)
    for task in ['6_1','7']:
        source=SECTION/f'cpp/figures/kadai{task}_results.csv'
        shutil.copyfile(source, ROOT/f'data/kadai{task}_results.csv')
        rows=list(csv.DictReader(source.open()))
        assert len(rows)==(400 if task=='6_1' else 800)
        summary['qr'+task]=summarize(rows,['residual','error','time','iterations'])
        new_plots(f'kadai{task}_results.csv',f'kadai{task}')
        if task=='7':
            summary['qr_paired_speedup']=[]
            for n in [10,20,40,80]:
                a={r['trial']:r for r in rows if int(r['n'])==n and r['method']=='Original QR'}
                b={r['trial']:r for r in rows if int(r['n'])==n and r['method']=='Shift + Deflation'}
                ratios=[float(a[i]['time'])/float(b[i]['time']) for i in a if np.isfinite(float(a[i]['time'])) and np.isfinite(float(b[i]['time']))]
                summary['qr_paired_speedup'].append({'n':n,'pairs':len(ratios),'median_ratio':float(np.median(ratios))})
    for csv_name, key, metrics in [
        ('paired_solvers.csv','paired',['residual','error','time']),
        ('power.csv','power',['residual','eigenvalue_error','eigenvector_error','time','iterations','spectral_ratio']),
        ('power_inverse.csv','power_inverse',['residual','eigenvalue_error','eigenvector_error','time','iterations'])]:
        rows=list(csv.DictReader((ROOT/'data'/csv_name).open()))
        assert len(rows)=={'paired':24,'power':400,'power_inverse':200}[key]
        summary[key]=summarize(rows,metrics)
    new_plots('power.csv','kadai4')
    new_plots('power_inverse.csv','kadai5')
    write_tables(summary)
    (ROOT/'data/summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
    sources=list((SECTION/'figures').glob('kadai[12]_1_*.svg'))+list((SECTION/'cpp/figures').glob('*.csv'))
    (ROOT/'data/source_hashes.json').write_text(json.dumps({str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2,ensure_ascii=False))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
