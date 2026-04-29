from __future__ import annotations

import os
import pandas as pd
import plotly.express as px
import streamlit as st

from career_agent.data_utils import load_jobs_file, read_resume_file
from career_agent.graph_builder import build_graph, graph_to_table
from career_agent.job_profile import (
    build_job_profiles,
    build_transition_paths,
    build_vertical_paths,
    summarize_profiles,
)
from career_agent.llm import LLMClient
from career_agent.matcher import match_student_to_jobs
from career_agent.reporting import build_report, check_report_completeness, polish_report
from career_agent.student_profile import calc_profile_scores, profile_from_text

st.set_page_config(page_title="大学生职业规划智能体", layout="wide")
st.title("基于 AI 的大学生职业规划智能体")
st.caption("覆盖岗位画像、岗位图谱、学生画像、人岗匹配与职业报告生成")

if "jobs_df" not in st.session_state:
    st.session_state.jobs_df = pd.DataFrame()
if "profiles" not in st.session_state:
    st.session_state.profiles = []
if "student_profile" not in st.session_state:
    st.session_state.student_profile = None
if "match_results" not in st.session_state:
    st.session_state.match_results = []
if "report_text" not in st.session_state:
    st.session_state.report_text = ""

llm = LLMClient()

with st.sidebar:
    st.subheader("系统状态")
    st.write(f"LLM 状态：{'已启用' if llm.enabled else '未配置（规则引擎模式）'}")
    st.write("建议上传企业完整岗位数据（10000 条）以提升画像准确性。")


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1) 岗位数据与画像",
    "2) 岗位关联图谱",
    "3) 学生就业能力画像",
    "4) 人岗匹配分析",
    "5) 职业发展报告",
])

with tab1:
    st.subheader("岗位数据加载")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        file = st.file_uploader("上传岗位数据（文件）", type=["csv", "xls", "xlsx"])
        if st.button("加载上传数据", use_container_width=True):
            try:
                st.session_state.jobs_df = load_jobs_file(file)
                st.success(f"已加载 {len(st.session_state.jobs_df)} 条岗位数据")
            except Exception as e:
                st.error(str(e))

    with col_b:
        if st.button("加载示例数据", use_container_width=True):
            sample_path = os.path.join("data", "sample_jobs.csv")
            st.session_state.jobs_df = pd.read_csv(sample_path)
            st.success(f"已加载示例数据 {len(st.session_state.jobs_df)} 条")

    if not st.session_state.jobs_df.empty:
        st.dataframe(st.session_state.jobs_df.head(20), use_container_width=True)

        if st.button("生成岗位画像（不少于 10 个）", type="primary"):
            profiles = build_job_profiles(st.session_state.jobs_df, llm=llm, min_profiles=10)
            st.session_state.profiles = profiles
            st.success(f"已生成 {len(profiles)} 个岗位画像")

    if st.session_state.profiles:
        st.subheader("岗位画像总览")
        summary_df = summarize_profiles(st.session_state.profiles)
        st.dataframe(summary_df, use_container_width=True)

with tab2:
    st.subheader("岗位关联图谱")

    if not st.session_state.profiles:
        st.info("请先在第 1 步生成岗位画像。")
    else:
        vertical_edges = build_vertical_paths(st.session_state.profiles)
        transition_paths = build_transition_paths(st.session_state.profiles, min_target_roles=5)
        graph = build_graph(vertical_edges, transition_paths)
        edges_df = graph_to_table(graph)

        c1, c2, c3 = st.columns(3)
        c1.metric("岗位节点数", graph.number_of_nodes())
        c2.metric("关联边数", graph.number_of_edges())
        c3.metric("可换岗岗位数", len(transition_paths))

        st.markdown("### 垂直晋升路径")
        if vertical_edges:
            st.table(pd.DataFrame(vertical_edges, columns=["当前岗位", "晋升岗位"]))
        else:
            st.warning("当前数据中未识别出明显级别词，可通过岗位命名规范增强。")

        st.markdown("### 换岗路径（每岗至少 2 条）")
        trans_rows = []
        for role, targets in transition_paths.items():
            trans_rows.append({"岗位": role, "换岗路径": " -> ".join([role] + targets[:2])})
        st.table(pd.DataFrame(trans_rows))

        st.markdown("### 关联图谱边列表")
        st.dataframe(edges_df, use_container_width=True)

with tab3:
    st.subheader("学生就业能力画像")

    resume_file = st.file_uploader("上传简历（TXT/PDF/DOCX）", type=["txt", "pdf", "docx"])
    manual_text = st.text_area("或手动录入简历内容", height=180)

    if st.button("生成学生能力画像", type="primary"):
        parsed_text = read_resume_file(resume_file)
        raw_text = (parsed_text + "\n" + manual_text).strip()
        profile = profile_from_text(raw_text, llm=llm)
        st.session_state.student_profile = profile
        score = calc_profile_scores(profile)
        st.success("学生画像生成完成")

        st.write("### 结构化画像")
        st.json(profile.model_dump())

        c1, c2 = st.columns(2)
        c1.metric("完整度评分", score["completeness"])
        c2.metric("竞争力评分", score["competitiveness"])

with tab4:
    st.subheader("人岗匹配分析")

    if not st.session_state.profiles or not st.session_state.student_profile:
        st.info("请先完成岗位画像与学生画像生成。")
    else:
        top_k = st.slider("返回匹配岗位数量", 3, 10, 5)
        if st.button("执行人岗匹配", type="primary"):
            results = match_student_to_jobs(st.session_state.student_profile, st.session_state.profiles, top_k=top_k)
            st.session_state.match_results = results

        if st.session_state.match_results:
            table = pd.DataFrame([
                {
                    "岗位": r.position_name,
                    "综合得分": r.weighted_score,
                    "基础要求": r.dimension_scores["basic_requirements"],
                    "职业技能": r.dimension_scores["professional_skills"],
                    "职业素养": r.dimension_scores["professional_literacy"],
                    "发展潜力": r.dimension_scores["development_potential"],
                }
                for r in st.session_state.match_results
            ])
            st.dataframe(table, use_container_width=True)

            fig = px.bar(
                table,
                x="岗位",
                y=["基础要求", "职业技能", "职业素养", "发展潜力"],
                barmode="group",
                title="四维能力匹配对比",
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("查看 Top1 匹配详情", expanded=True):
                top = st.session_state.match_results[0]
                st.write("优势：", "；".join(top.strengths) if top.strengths else "暂无")
                st.write("差距：", "；".join(top.gaps) if top.gaps else "暂无")
                st.write("建议：", "；".join(top.suggestions) if top.suggestions else "暂无")

with tab5:
    st.subheader("学生职业生涯发展报告")

    if not st.session_state.student_profile or not st.session_state.match_results:
        st.info("请先完成学生画像与人岗匹配。")
    else:
        if st.button("生成职业发展报告", type="primary"):
            report = build_report(
                st.session_state.student_profile,
                st.session_state.match_results,
                st.session_state.profiles,
            )
            st.session_state.report_text = report

        if st.session_state.report_text:
            report_text = st.text_area("报告编辑区", value=st.session_state.report_text, height=360)
            st.session_state.report_text = report_text

            col1, col2 = st.columns(2)
            with col1:
                if st.button("完整性检查", use_container_width=True):
                    missing = check_report_completeness(st.session_state.report_text)
                    if missing:
                        st.warning("缺失章节：" + "、".join(missing))
                    else:
                        st.success("报告章节完整")

            with col2:
                if st.button("智能润色", use_container_width=True):
                    st.session_state.report_text = polish_report(st.session_state.report_text, llm=llm)
                    st.success("润色完成")

            st.download_button(
                "一键导出 Markdown",
                data=st.session_state.report_text,
                file_name="career_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
