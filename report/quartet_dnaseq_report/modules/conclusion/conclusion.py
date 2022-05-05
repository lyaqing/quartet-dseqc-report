#!/usr/bin/env python

""" Quartet Metabolomics Report plugin module """

from __future__ import print_function
from collections import OrderedDict
import logging, math, os, re
import pandas as pd
import numpy as np
from multiqc import config
from multiqc.plots import table, heatmap
from multiqc.modules.base_module import BaseMultiqcModule

import plotly.express as px
import plotly.figure_factory as ff
from quartet_dnaseq_report.utils.plotly import plot as plotly_plot

# Initialise the main MultiQC logger
log = logging.getLogger('multiqc')

class MultiqcModule(BaseMultiqcModule):
  def __init__(self):
        
    # Halt execution if we've disabled the plugin
    if config.kwargs.get('disable_plugin', True):
      return None
    
    # Initialise the parent module Class object
    super(MultiqcModule, self).__init__(
      name='Assessment Summary'
    )
    # Add to self.css and self.js to be included in template
    self.css = {
        "assets/css/rank.css": os.path.join(
            os.path.dirname(__file__), "assets", "css", "rank.css"
        )
    }

    ### Load historical performance
    quartet_ref = pd.read_csv(os.path.join(os.path.dirname(__file__), 'assets', 'quartet_reference.txt'), sep='\t')
    if len(quartet_ref) == 0:
      log.debug('No file matched: conclusion/assets - quartet_reference.txt')
    
    ### Load user data
    # SUMMARY TABLE 1
    pr_list = []
    n = 0
    for f in self.find_log_files('conclusion/precision_recall_summary'):
      if f is None:
        log.debug('No file matched: conclusion - variants.calling.qc.txt')
      else:
        n = n + 1
        f_p = '%s/%s' % (f['root'], f['fn'])
        tmp_df = pd.read_csv(f_p, sep='\t')
        tmp_df[['SNV precision', 'INDEL precision', 'SNV recall', 'INDEL recall']] = round(tmp_df[['SNV precision', 'INDEL precision', 'SNV recall', 'INDEL recall']]/100, 4)
        one_set = ['Queried_Data_Set%s' % n, 'Queried', 'Queried_Data']
        for index, row in tmp_df.iterrows():
          if re.search('LCL5|D5', row.Sample):
            snv_D5_precision = row['SNV precision']; snv_D5_recall = row['SNV recall']
            indel_D5_precision = row['INDEL precision']; indel_D5_recall = row['INDEL recall']
          elif re.search('LCL6|D6', row.Sample):
            snv_D6_precision = row['SNV precision']; snv_D6_recall = row['SNV recall']
            indel_D6_precision = row['INDEL precision']; indel_D6_recall = row['INDEL recall']
          elif re.search('LCL7|F7', row.Sample):
            snv_F7_precision = row['SNV precision']; snv_F7_recall = row['SNV recall']
            indel_F7_precision = row['INDEL precision']; indel_F7_recall = row['INDEL recall']
          elif re.search('LCL8|M8', row.Sample):
            snv_M8_precision = row['SNV precision']; snv_M8_recall = row['SNV recall']
            indel_M8_precision = row['INDEL precision']; indel_M8_recall = row['INDEL recall']
        one_set.extend([snv_D5_precision, snv_D5_recall, snv_D6_precision, snv_D6_recall, snv_F7_precision, snv_F7_recall, snv_M8_precision, snv_M8_recall, indel_D5_precision, indel_D5_recall, indel_D6_precision, indel_D6_recall, indel_F7_precision, indel_F7_recall, indel_M8_precision, indel_M8_recall])
        pr_list.append(one_set)
    pr_df = pd.DataFrame(pr_list, columns=['sample', 'group', 'batch', 'snv_D5-precision', 'snv_D5-recall', 'snv_D6-precision', 'snv_D6-recall', 'snv_F7-precision', 'snv_F7-recall', 'snv_M8-precision', 'snv_M8-recall', 'indel_D5-precision', 'indel_D5-recall', 'indel_D6-precision', 'indel_D6-recall', 'indel_F7-precision', 'indel_F7-recall', 'indel_M8-precision', 'indel_M8-recall'])
    
    # SUMMARY TABLE 2
    mendelian_list = []
    n = 0
    for f in self.find_log_files('conclusion/mendelian_summary'):
      if f is None:
        log.debug('No file matched: conclusion - project_name.summary.txt')
      else:
        n = n + 1
        f_p = os.path.join(f['root'], f['fn'])
        tmp_df = pd.read_csv(f_p, sep='\t')
        one_set = ['Queried_Data_Set%s' % n, 'Queried', 'Queried_Data']
        snv_mendelian = tmp_df[tmp_df.Family.str.contains("SNV$")]['Mendelian_Concordance_Rate'].mean()
        indel_mendelian = tmp_df[tmp_df.Family.str.contains("INDEL$")]['Mendelian_Concordance_Rate'].mean()
        one_set.extend([snv_mendelian, indel_mendelian])
        mendelian_list.append(one_set)
    mendelian_df = pd.DataFrame(mendelian_list, columns=['sample', 'group', 'batch', 'snv_mendelian', 'indel_mendelian'])
    
    # Merge precision, indel, mendelian
    queried_performance = pr_df.merge(mendelian_df, on=['sample', 'group', 'batch'])
    queried_performance = queried_performance[quartet_ref.columns]
    # Rows of df takes a set of Quartet samples as a unit
    df = pd.concat([queried_performance, quartet_ref], axis=0)
    batches = df.batch.drop_duplicates().to_list()
    quality_metrics_list = []
    for bat in batches:
      precision_snv = df[df.batch == bat][[col for col in df.columns if re.search('snv.*precision', col)]].values.mean()
      precision_indel = df[df.batch == bat][[col for col in df.columns if re.search('indel.*precision', col)]].values.mean()
      recall_snv = df[df.batch == bat][[col for col in df.columns if re.search('snv.*recall', col)]].values.mean()
      recall_indel = df[df.batch == bat][[col for col in df.columns if re.search('indel.*recall', col)]].values.mean()
      mendelian_snv = df[df.batch == bat][[col for col in df.columns if re.search('snv.*mendelian', col)]].values.mean()
      mendelian_indel = df[df.batch == bat][[col for col in df.columns if re.search('indel.*mendelian', col)]].values.mean()
      # Calculate the total score
      beta2 = 0.5
      precision_beta = (1+beta2)*precision_snv*precision_indel/(beta2*precision_snv+precision_indel)
      recall_beta = (1+beta2)*recall_snv*recall_indel/(beta2*recall_snv+recall_indel)
      mendelian_beta = (1+beta2)*mendelian_snv*mendelian_indel/(beta2*mendelian_snv+mendelian_indel)
      total = sum([precision_beta, recall_beta, mendelian_beta])/3
      # precision_beta = precision_snv*5/6 + precision_indel*1/6
      # recall_beta = recall_snv*5/6 + recall_indel*1/6
      # mendelian_beta = mendelian_snv*5/6 + mendelian_indel*1/6
      # total = precision_beta * recall_beta * mendelian_beta
      quality_metrics_list.append([bat, round(precision_snv, 5), round(precision_indel, 5), round(recall_snv, 5), round(recall_indel, 5), round(mendelian_snv, 5), round(mendelian_indel, 5), round(total, 5)])
    quality_metrics_df = pd.DataFrame(quality_metrics_list, columns=['batch', 'precision_snv', 'precision_indel', 'recall_snv', 'recall_indel', 'mendelian_snv', 'mendelian_indel', 'total'])
    quality_metrics_df = pd.concat([quality_metrics_df, pd.DataFrame(columns=['precision_snv_performance', 'precision_indel_performance', 'recall_snv_performance', 'recall_indel_performance', 'mendelian_snv_performance', 'mendelian_indel_performance', 'total_performance'])])
    # Get performance categories
    # quantile_df =  quality_metrics_df.quantile([.25, .5, .75])
    # quantile_df = quantile_df.append(quantile_df.loc[.75] - quantile_df.loc[.25], ignore_index=True)
    # quantile_df.index = ['Q1', 'Q2', 'Q3', 'IQR']
    quantile_df =  quality_metrics_df.quantile([.15, .5, .85]); quantile_df.index = ['Q1', 'Q2', 'Q3']
    for index, row in quality_metrics_df.iterrows():
      for metric in ['precision_snv', 'precision_indel', 'recall_snv', 'recall_indel', 'mendelian_snv', 'mendelian_indel', 'total']:
        if row[metric] < quantile_df.loc['Q1', metric]:# - 1.5*quantile_df.loc['IQR', metric]:
          quality_metrics_df.loc[index, '%s_performance' % metric] = 'Bad'
        elif row[metric] < quantile_df.loc['Q2', metric]:
          quality_metrics_df.loc[index, '%s_performance' % metric] = 'Fair'
        elif row[metric] < quantile_df.loc['Q3', metric]:# + 1.5*quantile_df.loc['IQR', metric]:
          quality_metrics_df.loc[index, '%s_performance' % metric] = 'Good'
        else:
          quality_metrics_df.loc[index, '%s_performance' % metric] = 'Great'
    
    ### Evaluation metrics
    evaluation_metrics = []
    full_name = {'precision_snv': 'Precision (SNV)', 'precision_indel': 'Precision (INDEL)', 
                 'recall_snv': 'Recall (SNV)', 'recall_indel': 'Recall (INDEL)',
                 'mendelian_snv': 'Mendelian Concordance Rate (SNV)', 'mendelian_indel': 'Mendelian Concordance Rate (INDEL)',
                 'total': 'Total Score'}
    rank_df = quality_metrics_df[full_name.keys()].rank(axis=0, method='min', ascending=False)
    rank_df.insert(0, 'batch', quality_metrics_df.batch)
    
    for metric in full_name.keys():
      evaluation_metrics.append([full_name[metric], quality_metrics_df[quality_metrics_df.batch=='Queried_Data'][metric].to_list()[0], 
      '%.3f ± %.3f' % (quality_metrics_df[metric].mean(), quality_metrics_df[metric].std()), 
      '%.0f / %.0f' % (rank_df[rank_df.batch=='Queried_Data'][metric].to_list()[0], rank_df[metric].max()), 
      quality_metrics_df[quality_metrics_df.batch=='Queried_Data']['%s_performance'  % metric].to_list()[0]])
    
    evaluation_metrics_df = pd.DataFrame(evaluation_metrics, columns=['Quality Metrics', 'Value', 'Historical value (mean ± SD)', 'Rank', 'Performance'])
    table_summary_dic = evaluation_metrics_df.set_index('Quality Metrics').T.to_dict()
    
    overview_data = quality_metrics_df[['batch', 'total', 'total_performance']]
    rank_slim = rank_df[['batch', 'total']]; rank_slim.columns = ['batch', 'rank']
    overview_data = overview_data.merge(rank_slim, on='batch')
    if len(table_summary_dic) != 0:
      self.plot_summary_table('conclusion_summary', table_summary_dic, overview_data)
    else:
      log.debug('No file matched: conclusion - conclusion_table.tsv')
    
    ### Plot for the performance of SNV and INDEL
    df = pd.concat([df, pd.DataFrame(columns=['snv_f1', 'indel_f1'])])
    for index, row in df.iterrows():
      snv_f1 = []; indel_f1 = []
      for sample in ['D5', 'D6', 'F7', 'M8']:
        p1 = row.filter(regex='snv_%s-precision' % sample).to_list()[0]
        r1 = row.filter(regex='snv_%s-recall' % sample).to_list()[0]
        snv_f1.append(2 * p1 * r1/(p1 + r1))
        p2 = row.filter(regex='indel_%s-precision' % sample).to_list()[0]
        r2 = row.filter(regex='indel_%s-recall' % sample).to_list()[0]
        indel_f1.append(2 * p2 * r2/(p2 + r2))
      df.loc[index, 'snv_f1'] = sum(snv_f1)/len(snv_f1)
      df.loc[index, 'indel_f1'] = sum(indel_f1)/len(indel_f1)
    
    fig_data = df[['sample', 'group', 'snv_f1', 'snv_mendelian']]
    fig_data.columns = ['Batch', 'Group', 'F1-score', 'Mendelian Concordance Rate']
    self.plot_mcr_f1_scatter('snv_performance', fig_data, title='SNV Performance', section_name='Performance of SNV and INDELs', description = """Due to the apparent differences between SNV and INDEL, the performance of the two types of small variants of the evaluated data compared to the Quartet historical batches is shown separately in this section. Each data point represents a set of Quartet samples, i.e., one each of D5, D6, F7, and M8.""")
    fig_data = df[['sample', 'group', 'indel_f1', 'indel_mendelian']]
    fig_data.columns = ['Batch', 'Group', 'F1-score', 'Mendelian Concordance Rate']
    self.plot_mcr_f1_scatter('indel_performance', fig_data, title='INDEL Performance', section_name='', description='')
    
    ### Historical scores
    quality_score_df = quality_metrics_df
    quality_score_df.sort_values('total', inplace=True, ascending=True)
    if quality_score_df.shape[0] != 0:
      self.plot_quality_score('plot_quality_score', quality_score_df, full_name)
    else:
      log.debug('No file matched: conclusion - warning!')
  

  ### Function 1: Evaluation metrics
  def plot_summary_table(self, id, table_data, overview_data, title='', section_name='', description=None):
    # Overview
    overview_data.sort_values('total', inplace=True, ascending=True)
    # Calculate percentage
    total = overview_data.shape[0]
    bad = "%.2f%s" % (int(overview_data.total_performance.value_counts().to_dict()['Bad'])/total * 100, '%')
    fair = "%.2f%s" % (int(overview_data.total_performance.value_counts().to_dict()['Fair'])/total * 100, '%')
    good = "%.2f%s" % (int(overview_data.total_performance.value_counts().to_dict()['Good'])/total * 100, '%')
    great = "%.2f%s" % (int(overview_data.total_performance.value_counts().to_dict()['Great'])/total * 100, '%')
    queried = "%.2f%s" % (overview_data[overview_data.batch == 'Queried_Data']['rank'].mean()/total * 100, '%')
    queried_double = "%.2f%s" % (((total-overview_data[overview_data.batch == 'Queried_Data']['rank'].mean())*2/total+1/total) * 100, '%')
    # print(queried_double)
    overview_html = """
    <div class="progress">
      <div class="progress-bar progress-bar-bad" style="width: {bad}" data-toggle="tooltip" title="" data-original-title="">Bad</div>
      <div class="progress-bar progress-bar-fair" style="width: {fair}" data-toggle="tooltip" title="" data-original-title="">Fair</div>
      <div class="progress-bar progress-bar-good" style="width: {good}" data-toggle="tooltip" title="" data-original-title="">Good</div>
      <div class="progress-bar progress-bar-great" style="width: {great}" data-toggle="tooltip" title="" data-original-title="">Great</div>
    </div>
    
    <div class="arrow" style="width: {queried_double}">
      <svg class="tangle" transform="translate(0 -25)">
      </svg>
      <span class="label"> {queried} </span>
    </div>
    """.format(bad=bad, fair=fair, good=good, great=great, queried_double=queried_double, queried='Your dataset')
    
    # Table
    headers = OrderedDict()
    headers['Value'] = {
      'title': 'Value',
      'description': 'Value',
      'scale': False,
      'format': '{0:.3f}'
    }
    headers['Historical value (mean ± SD)'] = {
      'title': 'Historical Value',
      'description': 'Historical Value (mean ± SD)',
      'scale': False,
      'format': '{0:.2f}'
    }
    headers['Rank'] = {
      'title': 'Rank',
      'description': 'Rank',
      'scale': False,
      'format': '{:.0f}'
    }
    headers['Performance'] = {
      'title': 'Performance',
      'description': 'Performance',
      'scale': False,
      'format': '{:.0f}',
      "cond_formatting_rules": {
        "green": [{"s_eq": "Great"}],
        "lightgreen": [{"s_eq": "Good"}],
        "orange": [{"s_eq": "Fair"}],
        "red": [{"s_eq": "Bad"}]
        },
      "cond_formatting_colours": [
        {"green": "#0f9115"},
        {"lightgreen": "#70c402"},
        {"orange": "#d97c11"},
        {"red": "#b80d0d"}
        ]
    }
    table_config = {
      'namespace': 'conclusion_summary',
      'id': id,
      'table_title': '',
      'col1_header': 'Quality Metrics',
      'no_beeswarm': True,
      'sortRows': False
    }
    table_html = table.plot(table_data, headers, table_config)
    
    # Add a report section with the table
    self.add_section(
      name = 'Evaluation metrics',
      anchor = id + '_anchor',
      description = """
      The submitted data to be tested can be divided into 4 levels based on the Quartile Index of the metrics scores by comparing with historical batches: <span style="color: #b80d0d;font-weight:bold">Bad</span>, <span style="color: #d97c11;font-weight:bold">Fair</span>, <span style="color: #70c402;font-weight:bold">Good</span>, <span style="color: #0f9115;font-weight:bold">Great</span>.<br>
      The total score was obtained by weighting the performance of SNV and INDEL in terms of Precision, Recall, and MCR. Please see Methods for details.
      """,
      plot = overview_html + '\n' + table_html
    )
  

  ### Function 2: Historical scores
  def plot_quality_score(self, id, quality_score_df, full_name, title=None, section_name=None, description=None, helptext=None):
    # After transposing, there are 3 rows and n columns
    final_data = quality_score_df[list(full_name.keys())].T.values.tolist()
    final_xcats = quality_score_df['batch'].to_list()
    final_ycats = list(full_name.values())
    
    pconfig = {
      "id": id,
      "xTitle": "Performance of batches gradually increases from left to right",
      "yTitle": "Evaluation metrics",
      "decimalPlaces": 4,
      "square": False,
      "xcats_samples": False,
      "reverseColors": True,
    }
    
    self.add_section(
      name="Historical scores",
      anchor= id + '_anchor',
      description="""
      Scores of evaluation metrics for the current batch and all historical batches assessed. The name of your data is <span style="background-color: transparent;font-weight:bold">Queried_Data</span>.
      """,
      plot=heatmap.plot(final_data, final_xcats, final_ycats, pconfig),
    )
  

  ### Function 3: Plot SNV or INDEL based on reference datasets table and scatter plot
  def plot_mcr_f1_scatter(self, id, fig_data, title=None, section_name=None, description=None, helptext=None):
    fig = px.scatter(fig_data, 
          x = 'Mendelian Concordance Rate', y = 'F1-score',
          symbol = 'Group',
          symbol_map = {"PCR": 0, "PCR-free": 0, "Queried": 18},
          title = title, 
          color = 'Group', 
          color_discrete_map={"PCR": "#2f5c85", "PCR-free": "#7ba1c7", "Queried": "#bb1616"},
          marginal_y='box', marginal_x='box', 
          hover_data={'Mendelian Concordance Rate': ':.3f', 'F1-score': ':.3f', 'Batch': True})
    
    fig.update_traces(marker=dict(size=10, line_color='white', line_width=0.5))
    fig.update_layout(xaxis_title='Mendelian Concordance Rate',
                      yaxis_title='F1-score',
                      font=dict(family="Arial, sans-serif",
                                size=12.5,
                                color="black"),
                      template="simple_white")

    html = plotly_plot(fig, {
          'id': id + '_plot',
          'data_id': id + '_data',
          'title': title,
          'auto_margin': True
          })
    
    # Add a report section with the scatter plot
    self.add_section(
        name = section_name,
        anchor = id + '_anchor',
        description = description,
        helptext = '',
        plot = html
    )

