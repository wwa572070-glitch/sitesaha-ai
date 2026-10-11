from sitesaha.rag import classify_question


def test_safety_intents():
    assert classify_question("有人触电了怎么办？") == "紧急情况"
    assert classify_question("脚手架有点晃还能上吗？") == "高风险作业"
    assert classify_question("我是第一次上工地") == "新人入场"
    assert classify_question("电钻怎么操作？") == "操作流程"
