# FIO 命令生成器 - 使用 LLM 将测试需求转换为 FIO 命令
from typing import Tuple, Optional, List
import json
import re
import requests


class FIOCommandGenerator:
    """
    FIO 命令生成器
    使用 LLM 将用户的测试需求转换为标准的 FIO 命令
    """
    
    def __init__(self, api_url: str, api_key: str, model: str):
        """
        初始化 FIO 命令生成器
        参数：
            api_url - LLM API 地址
            api_key - API 密钥
            model - 模型名称
        """
        self.api_url = api_url.rstrip('/').rstrip(',')
        self.api_key = api_key
        self.model = model
    
    def generate_commands(self, test_requirement: str) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """
        根据测试需求生成 FIO 命令
        参数：
            test_requirement - 用户输入的测试需求
        返回：(是否成功，错误信息，FIO 命令列表)
        """
        prompt = self._build_prompt(test_requirement)
        response = self._call_llm(prompt)
        
        if not response:
            return False, "LLM 调用失败", None
        
        commands = self._parse_commands(response)
        if not commands:
            return False, "未能解析出有效的 FIO 命令", None
        
        return True, None, commands
    
    def _build_prompt(self, test_requirement: str) -> str:
        """
        构建 LLM 提示词
        参数：
            test_requirement - 测试需求
        返回：提示词
        """
        return f"""你是一个专业的存储性能测试工程师，擅长使用 fio 工具进行 NVMe SSD 性能测试。
请根据以下测试需求，参考提供的 FIO 命令模板，生成标准的 fio 命令。

## FIO 命令模板参考

模板1 - 填盘命令（顺序写满盘）：
fio --name=IoExerciserFio-nvme0n1-0-1753-72d4f1 --filename=/dev/nvme0n1 --thread --ioengine=libaio --stonewall --group_reporting --exitall_on_error=1 --cpus_allowed_policy=split --direct=1 --randrepeat=0 --allrandrepeat=0 --randseed=3549154694 --rw=write --bs=128k --iodepth=512 --numjobs=1 --loops=1

模板2 - 128k QD16 顺序读测试：
fio --name=IoExerciserFio-nvme0n1-1-9374-009709 --filename=/dev/nvme0n1 --thread --ioengine=libaio --stonewall --group_reporting --exitall_on_error=1 --cpus_allowed_policy=split --output-format=normal,json+ --direct=1 --randrepeat=0 --allrandrepeat=0 --randseed=526559762 --rw=read --bs=128k --ba=128k --iodepth=16 --numjobs=1 --time_based --runtime=10m --percentile_list=50.0:90:99:99.9:99.99:99.999:99.9999:99.99999:99.999999:99.9999999:100 --log_avg_msec=1000 --per_job_logs=0

## 生成规则

1. 每条命令必须是完整可执行的 fio 命令，以 fio 开头
2. 必须参考模板的参数风格，包含以下关键公共参数：
   --thread --ioengine=libaio --stonewall --group_reporting --exitall_on_error=1 --cpus_allowed_policy=split --direct=1 --randrepeat=0 --allrandrepeat=0
3. --filename 使用 /dev/nvme0n1
4. --name 格式参考模板，使用 IoExerciserFio-nvme0n1-序号-随机数-随机hex 的格式
5. --randseed 使用随机数
6. 根据测试需求设置 --rw（read/write/randread/randwrite/rw/randrw）、--bs、--iodepth、--numjobs 等参数
7. 性能测试（非填盘）需添加 --time_based --runtime=10m --output-format=normal,json+ --log_avg_msec=1000 --per_job_logs=0
8. 填盘命令使用 --loops=1，不使用 --time_based
9. 顺序读写需添加 --ba 参数（等于 --bs 的值）
10. 输出格式必须严格遵循以下格式，不要有任何额外说明：
   ```
   fio --name=xxx --filename=/dev/nvme0n1 ...
   fio --name=xxx --filename=/dev/nvme0n1 ...
   ```
11. 根据测试需求生成合适的命令，通常 1-5 条命令
12. 不要输出命令以外的任何内容，不要解释说明

测试需求：
{test_requirement}

请输出 FIO 命令（每条命令一行）：
"""
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        调用 LLM 模型
        参数：
            prompt - 提示词
        返回：LLM 响应
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的存储性能测试工程师，擅长使用 fio 工具。请严格按照要求的格式输出 FIO 命令，不要有任何额外说明。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.3
            }
            
            chat_url = self.api_url + '/chat/completions'
            response = requests.post(chat_url, headers=headers, json=data, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                return content
            
            return None
            
        except Exception as e:
            print(f"[FIO] 调用 LLM 失败：{e}")
            return None
    
    def _parse_commands(self, response: str) -> List[str]:
        """
        从 LLM 响应中解析 FIO 命令
        参数：
            response - LLM 响应文本
        返回：FIO 命令列表
        """
        commands = []
        
        # 提取代码块中的内容（如果有 ``` 标记）
        code_block_pattern = r"```(?:bash|shell)?\s*([\s\S]*?)\s*```"
        code_blocks = re.findall(code_block_pattern, response)
        
        if code_blocks:
            # 从代码块中提取命令
            for block in code_blocks:
                lines = block.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('fio '):
                        commands.append(line)
        else:
            # 直接按行提取，查找以 fio 开头的行
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('fio '):
                    commands.append(line)
        
        # 清理命令中的多余空格
        commands = [re.sub(r'\s+', ' ', cmd).strip() for cmd in commands if cmd]
        
        return commands
