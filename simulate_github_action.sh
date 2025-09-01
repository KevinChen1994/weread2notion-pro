#!/bin/bash

echo "🤖 GitHub Action 本地模拟器"
echo "=" | head -c 50 | tr '\n' '='
echo ""

# 设置模拟的GitHub环境变量
export GITHUB_WORKSPACE=$(pwd)
export GITHUB_REPOSITORY="local/weread2notion-pro"
export GITHUB_REF="refs/heads/main"
export GITHUB_SHA="local-development"
export GITHUB_ACTOR="local-user"
export GITHUB_RUN_ID=$(uuidgen)
export GITHUB_RUN_NUMBER="1"
export CI="true"
export RUNNER_OS="Local"

# 设置年份（如果未设置）
if [ -z "$YEAR" ]; then
    export YEAR=$(date +"%Y")
fi

# 加载.env文件
if [ -f ".env" ]; then
    echo "📋 加载环境变量..."
    # 使用source而不是export，避免特殊字符解析问题
    set -a  # 自动导出所有变量
    source .env
    set +a  # 关闭自动导出
    echo "✅ 环境变量已加载"
else
    echo "⚠️  未找到.env文件"
fi

# 检查必需的环境变量
check_env_vars() {
    echo "🔍 检查环境变量..."
    
    required_vars=("NOTION_TOKEN" "NOTION_PAGE")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo "❌ 缺少必需的环境变量: ${missing_vars[*]}"
        echo "请在.env文件中配置这些变量"
        return 1
    fi
    
    echo "✅ 环境变量检查通过"
    return 0
}

# 设置Python环境
setup_python() {
    echo "📦 设置Python环境..."
    
    echo "  - 升级pip..."
    python -m pip install --upgrade pip > /dev/null 2>&1
    
    echo "  - 安装依赖..."
    pip install -r requirements.txt > /dev/null 2>&1
    
    echo "✅ Python环境设置完成"
}

# 微信读书同步工作流
run_weread_workflow() {
    echo ""
    echo "📚 执行微信读书同步工作流"
    echo "-" | head -c 30 | tr '\n' '-'
    echo ""
    
    echo "📖 步骤1: 书籍同步..."
    if python -m weread2notionpro.book; then
        echo "✅ 书籍同步完成"
    else
        echo "❌ 书籍同步失败"
        return 1
    fi
    
    echo "✏️ 步骤2: 划线和笔记同步..."
    if python -m weread2notionpro.weread; then
        echo "✅ 划线和笔记同步完成"
    else
        echo "❌ 划线和笔记同步失败"
        return 1
    fi
    
    echo "🎉 微信读书同步工作流完成"
}

# 阅读时间同步工作流
run_read_time_workflow() {
    echo ""
    echo "⏰ 执行阅读时间同步工作流"
    echo "-" | head -c 30 | tr '\n' '-'
    echo ""
    
    echo "🧹 步骤1: 清理输出文件夹..."
    rm -rf ./OUT_FOLDER 2>/dev/null || true
    echo "✅ 清理完成"
    
    echo "🎨 步骤2: 生成阅读热力图..."
    
    # 设置默认值
    NAME=${NAME:-"WeRead User"}
    background_color=${background_color:-"#FFFFFF"}
    track_color=${track_color:-"#ACE7AE"}
    special_color=${special_color:-"#69C16E"}
    special_color2=${special_color2:-"#549F57"}
    dom_color=${dom_color:-"#EBEDF0"}
    text_color=${text_color:-"#000000"}
    
    # 生成热力图
    if github_heatmap weread \
        --year $YEAR \
        --me "$NAME" \
        --without-type-name \
        --background-color=$background_color \
        --track-color=$track_color \
        --special-color1=$special_color \
        --special-color2=$special_color2 \
        --dom-color=$dom_color \
        --text-color=$text_color; then
        echo "✅ 热力图生成完成"
    else
        echo "❌ 热力图生成失败"
        return 1
    fi
    
    echo "📝 步骤3: 重命名热力图文件..."
    if [ -d "OUT_FOLDER" ] && [ -f "OUT_FOLDER/weread.svg" ]; then
        cd OUT_FOLDER
        # 删除其他文件，只保留weread.svg
        find . -type f ! -name "weread.svg" -exec rm -f {} + 2>/dev/null || true
        cd ..
        
        # 生成随机文件名
        RANDOM_FILENAME=$(uuidgen).svg
        mv ./OUT_FOLDER/weread.svg ./OUT_FOLDER/$RANDOM_FILENAME
        echo "✅ 文件已重命名为: $RANDOM_FILENAME"
    else
        echo "⚠️  未找到热力图文件"
    fi
    
    echo "📤 步骤4: Git提交（可选）..."
    if git status > /dev/null 2>&1; then
        git config --local user.email "action@local.com" 2>/dev/null || true
        git config --local user.name "Local GitHub Action" 2>/dev/null || true
        git add . 2>/dev/null || true
        git commit -m 'add new heatmap (local)' 2>/dev/null || echo "  - 没有新的更改需要提交"
    else
        echo "  - 不在Git仓库中，跳过提交"
    fi
    
    echo "📊 步骤5: 阅读时间同步..."
    if python -m weread2notionpro.read_time; then
        echo "✅ 阅读时间同步完成"
    else
        echo "❌ 阅读时间同步失败"
        return 1
    fi
    
    echo "🎉 阅读时间同步工作流完成"
}

# 主逻辑
main() {
    # 检查参数
    if [ $# -eq 0 ]; then
        echo "使用方法:"
        echo "  $0 weread      # 微信读书同步工作流"
        echo "  $0 read_time   # 阅读时间同步工作流"
        echo "  $0 all         # 执行所有工作流"
        echo ""
        echo "说明:"
        echo "  - 确保已配置好 .env 文件"
        echo "  - 工作流将按照GitHub Action的步骤执行"
        exit 1
    fi

    # 检查环境
    if ! check_env_vars; then
        exit 1
    fi

    # 设置Python环境
    setup_python

    # 执行指定的工作流
    case "$1" in
        "weread")
            if run_weread_workflow; then
                echo ""
                echo "🎉 微信读书同步工作流执行成功"
            else
                echo ""
                echo "❌ 微信读书同步工作流执行失败"
                exit 1
            fi
            ;;
        "read_time")
            if run_read_time_workflow; then
                echo ""
                echo "🎉 阅读时间同步工作流执行成功"
            else
                echo ""
                echo "❌ 阅读时间同步工作流执行失败"
                exit 1
            fi
            ;;
        "all")
            if run_weread_workflow && run_read_time_workflow; then
                echo ""
                echo "🎉 所有工作流执行成功"
            else
                echo ""
                echo "❌ 工作流执行失败"
                exit 1
            fi
            ;;
        *)
            echo "❌ 未知的工作流: $1"
            echo "支持的工作流: weread, read_time, all"
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
