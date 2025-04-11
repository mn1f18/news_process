本文介绍调用百炼应用时的输入输出参数。

相关指南：请参考应用调用。

调用方式
您可以使用DashScope SDK或HTTP接口调用百炼的应用（智能体、工作流或智能体编排）。

如果您在应用内选择了DeepSeek大语言模型，请参见DeepSeek系列模型应用调用。

您可以通过本文默认的公网终端节点https://dashscope.aliyuncs.com/api/v1/访问百炼平台，也可以通过私网终端节点访问百炼平台以提高数据传输的安全性及传输效率。

您需要已创建百炼应用，获取API Key并配置API Key到环境变量。如果通过SDK调用，还需要安装DashScope SDK。
请求体
请求示例
单轮对话多轮对话参数传递流式输出检索知识库长期记忆上传文件
PythonJavaHTTP
请求示例

 
import os
from http import HTTPStatus
from dashscope import Application
response = Application.call(
    # 若没有配置环境变量，可用百炼API Key将下行替换为：api_key="sk-xxx"。但不建议在生产环境中直接将API Key硬编码到代码中，以减少API Key泄露风险。
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    app_id='YOUR_APP_ID',# 替换为实际的应用 ID
    prompt='你是谁？')

if response.status_code != HTTPStatus.OK:
    print(f'request_id={response.request_id}')
    print(f'code={response.status_code}')
    print(f'message={response.message}')
    print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
else:
    print(response.output.text)
app_id string （必选）

应用的标识。

在应用列表页面的应用卡片上可以获取应用ID。

Java SDK中为appId。通过HTTP调用时，请将实际的应用ID放入 URL 中，替换YOUR_APP_ID。
prompt string （必选）

输入当前期望应用执行的指令prompt，用来指导应用生成回复。

暂不支持传入文件。如果应用使用的是Qwen-Long模型，应用调用方法与其他模型一致。

当您通过传入messages自己管理对话历史时，则无需传递prompt。

通过HTTP调用时，请将 prompt 放入 input 对象中。
session_id string （可选）

历史对话的唯一标识。

传入session_id时，请求将自动携带云端存储的对话历史。具体用法请参考多轮对话。

传入session_id时，prompt为必传。
若同时传入session_id和messages，则优先使用传入的messages。
目前仅智能体应用和对话型工作流应用支持多轮对话。
Java SDK中为setSessionId。通过HTTP调用时，请将 session_id 放入 input 对象中。
messages array （可选）

由历史对话组成的消息列表。

用于自主管理上下文实现多轮对话，具体用法请参考多轮对话。

核心规则：

当使用 messages 管理对话时，无需传递 prompt；

若同时传入 messages 和 prompt：

prompt 会被转换为一条 {"role": "user", "content": "您的prompt"}，自动追加到 messages 末尾，生成最终上下文。

示例：

 
// 原始传入
{
  "messages": [{"role": "user", "content": "你好"}], 
  "prompt": "推荐一部电影"
}
// 实际生效的messages
[
  {"role": "user", "content": "你好"}, 
  {"role": "user", "content": "推荐一部电影"}
]
若同时传入session_id和messages，则大模型优先使用messages中的内容，session_id将被忽略。

目前仅智能体应用和对话型工作流应用支持多轮对话。
通过HTTP调用时，请将messages 放入 input 对象中。
使用该参数，Python Dashscope SDK的版本至少应为1.20.14，Java Dashscope SDK的版本至少应为2.17.0。
消息类型

workspace string （可选）

业务空间标识。

调用子业务空间的应用时需传递workspace标识，调用默认业务空间的应用时无需传递workspace。

在子业务空间里，点击应用列表页面的应用卡片上的调用，即可在应用API代码中获取子业务空间的workspace标识，具体请参考获取Workspace ID。

通过HTTP调用时，请指定Header中的 X-DashScope-WorkSpace。
stream boolean（可选）

是否流式输出回复。

参数值：

false（默认值）：模型生成完所有内容后一次性返回结果。

true：边生成边输出，即每生成一部分内容就立即输出一个片段（chunk）。

Java SDK中为streamCall。通过HTTP调用时，请指定Header中的 X-DashScope-SSE 为 enable。
incremental_output boolean（可选）

在流式输出模式下是否开启增量输出。

参数值：

false（默认值）：每次输出当前已经生成的整个序列，最终输出为完整结果。

 
I
I like
I like apple
I like apple.
true：增量输出，即后续输出内容不包含已输出的内容。您需要实时地逐个读取这些片段以获得完整的结果。

 
I
like
apple
.
Java SDK中为incrementalOutput。通过HTTP调用时，请将incremental_output放入parameters对象中。
flow_stream_mode object（可选）

工作流应用的流式输出模式。具体使用方法请参考流式输出。

参数值及使用方法如下：

full_thoughts（默认值）：

描述：所有节点的流式结果在thoughts字段中输出。

要求：同时必须要设置has_thoughts为True。

agent_format：

描述：使用与智能体应用相同的输出模式。

效果：在控制台应用中，可选择打开指定节点的结果返回开关，则该节点的流式结果将在output的text字段中输出。

场景：适合只关心中间指定节点输出的场景。

结果返回开关当前仅支持文本转换节点、大模型节点以及结束节点（结束节点默认打开）。
在并行节点中同时开启结果返回开关，会导致内容混杂。因此，开启开关的节点需要有明确的输出先后顺序。
Java SDK中暂未开放此参数。通过HTTP调用时，请将flow_stream_mode放入parameters对象中。
biz_params object （可选）

应用通过自定义节点或自定义插件传递参数时，使用该字段进行传递。具体使用方法请参考自定义参数传递。

Java SDK中为bizParams，通过HTTP调用时，请将 biz_params 放入 input 对象中。
属性

memory_id string （可选）

长期记忆体ID。

在百炼控制台应用中打开长期记忆开关并发布应用，通过指定 memory_id 调用应用时，系统依据用户偏好信息自动构建和保存长期记忆。后续使用同一 memory_id 调用时，系统会恢复这些长期记忆，并与最新的用户消息合并提供给模型处理。

memory_id的创建方法请参见CreateMemory。详细调用方法请参见长期记忆。

Java SDK中为memoryId。通过HTTP调用时，请将 memory_id 放入input 对象中。
目前仅智能体应用支持长期记忆。
has_thoughts boolean （可选）

是否输出插件调用、知识检索的过程，或DeepSeek-R1 类模型思考过程。

参数值：

True：输出在thoughts字段中。

False（默认值）：不输出。

调用智能体应用实现Prompt样例库时，需要将此参数设置为True。

Java SDK中为hasThoughts。通过HTTP调用时，请将 has_thoughts 放入 parameters 对象中。
image_list Array （可选）

图片链接列表。用于传递图片链接。

支持以下两种使用场景：

图片检索：在智能体应用中，根据上传的图片链接，检索包含图片链接的结构化知识库。

图片理解：在通义千问VL模型的智能体应用中，还可以直接提问图片内容。

 
"image_list" : ["https://example.com/images/example.jpg"]
#这是一个虚构的URL，请替换为实际存在的图片URL
可以是多个，每个图片链接之间通过英文逗号分隔。
Java SDK中为images。通过HTTP调用时，请将 image_list 放入 input 对象中。
rag_options Array （可选）

用于配置与检索相关的参数。包括但不限于对指定的知识库或文档进行检索。详细用法和规则请参见检索知识库。

Java SDK中为ragOptions。通过HTTP调用时，请将 rag_options 放入 parameters 对象中。
目前仅智能体应用（包括RAG应用）支持此类检索参数。
属性

响应对象
响应示例
status_code integer

返回的状态码。

200表示请求成功，否则表示请求失败。可以通过code获取错误码，通过message字段获取错误详细信息。

Java SDK不会返回该参数。调用失败会抛出异常，异常信息为code和message的内容。
单轮对话响应示例

 
{
    "output": {
        "finish_reason": "stop",
        "session_id": "6105c965c31b40958a43dc93c28c7a59",
        "text": "我是通义千问，由阿里云开发的AI助手。我被设计用来回答各种问题、提供信息和与用户进行对话。有什么我可以帮助你的吗？"
    },
    "usage": {
        "models": [
            {
                "output_tokens": 36,
                "model_id": "qwen-plus",
                "input_tokens": 74
            }
        ]
    },
    "request_id": "f97ee37d-0f9c-9b93-b6bf-bd263a232bf9"
}
指定知识库响应示例

调用应用指定知识库功能时想要输出召回文档中被模型引用的文档信息，可在百炼控制台的智能体应用内，单击检索配置打开展示回答来源开关并发布应用。

 
{
    "text": "根据您的预算，我推荐您考虑百炼 Zephyr Z9。这款手机轻巧便携，拥有6.4英寸1080 x 2340像素的屏幕，搭配128GB存储与6GB RAM，非常适合日常使用<ref>[1]</ref>。此外，它还配备了4000mAh电池以及30倍数字变焦镜头，能够捕捉远处细节，价格区间在2499-2799元之间，完全符合您的预算需求<ref>[1]</ref>。",
    "finish_reason": "stop",
    "session_id": "6c1d47fa5eca46b2ad0668c04ccfbf13",
    "thoughts": null,
    "doc_references": [
        {
            "index_id": "1",
            "title": "百炼手机产品介绍",
            "doc_id": "file_7c0e9abee4f142f386e488c9baa9cf38_10317360",
            "doc_name": "百炼系列手机产品介绍",
            "doc_url": null,
            "text": "【文档名】:百炼系列手机产品介绍\n【标题】:百炼手机产品介绍\n【正文】:参考售价：5999- 6499。百炼 Ace Ultra ——游戏玩家之选：配备 6.67英寸 1080 x 2400像素屏幕，内置 10GB RAM与 256GB存储，确保游戏运行丝滑无阻。百炼 Ace Ultra ——游戏玩家之选：配备 6.67英寸 1080 x 2400像素屏幕，内置 10GB RAM与 256GB存储，确保游戏运行丝滑无阻。5500mAh电池搭配液冷散热系统，长时间游戏也能保持冷静。高动态双扬声器，沉浸式音效升级游戏体验。参考售价：3999- 4299。百炼 Zephyr Z9 ——轻薄便携的艺术：轻巧的 6.4英寸 1080 x 2340像素设计，搭配 128GB存储与 6GB RAM，日常使用游刃有余。4000mAh电池确保一天无忧，30倍数字变焦镜头捕捉远处细节，轻薄而不失强大。参考售价：2499- 2799。百炼 Flex Fold+ ——折叠屏新纪元：集创新与奢华于一身，主屏 7.6英寸 1800 x 2400像素与外屏 4.7英寸 1080 x 2400像素，多角度自由悬停设计，满足不同场景需求。512GB存储、12GB RAM，加之 4700mAh电池与 UTG超薄柔性玻璃，开启折叠屏时代新篇章。此外，这款手机还支持双卡双待、卫星通话，帮助您在世界各地都能畅联通话。参考零售价：9999- 10999。\n",
            "biz_id": null,
            "images": [

            ],
            "page_number": [
                0]
        }]
}
异常响应示例

在访问请求出错的情况下，输出的结果中会通过 code 和 message 指明错误原因。

此处以未传入正确API-KEY为例，向您展示异常响应的示例。

 
request_id=1d14958f-0498-91a3-9e15-be477971967b, 
code=401, 
message=Invalid API-key provided.
request_id string

当前的请求ID。

Java SDK返回参数为requestId。
code string

表示错误码，调用成功时为空值。

详情请参见错误信息。

该参数仅支持Python SDK。
message string

表示失败详细信息，成功忽略。

该参数仅支持Python SDK。
output object

表示调用结果信息。

output属性

text string

模型生成的回复内容。

finish_reason string

完成原因。

正在生成时为null，生成结束时如果由于停止token导致则为stop。

session_id string

当前对话的唯一标识。

在后续请求中传入，可携带历史对话记录。

thoughts array

调用时将has_thoughts参数设置为True，即可在thoughts中查看插件调用、知识检索的过程，或DeepSeek-R1 类模型思考过程。

thoughts属性

doc_references array

检索的召回文档中被模型引用的文档信息。

在百炼控制台的智能体应用内，单击检索配置打开展示回答来源开关并发布应用，doc_references才可能包含有效信息。

doc_references属性

usage object

表示本次请求使用的数据信息。

usage属性

models array

本次应用调用到的模型信息。

models属性

model_id string

本次应用调用到的模型 ID。

input_tokens integer

用户输入文本转换成Token后的长度。

output_tokens integer

模型生成回复转换为Token后的长度。


通义千问API参考
更新时间：2025-04-07 10:54:08
产品详情
我的收藏
本文介绍通义千问 API 的输入输出参数。

模型介绍、选型建议和使用方法，请参考文本生成。
您可以通过 OpenAI 兼容或 DashScope 的方式调用通义千问 API。

OpenAI 兼容
公有云金融云
使用SDK调用时需配置的base_url：https://dashscope.aliyuncs.com/compatible-mode/v1

使用HTTP方式调用时需配置的endpoint：POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

您需要已获取API Key并配置API Key到环境变量。如果通过OpenAI SDK进行调用，还需要安装SDK。
请求体
文本输入流式输出图像输入视频输入工具调用联网搜索异步调用文档理解文字提取
此处以单轮对话作为示例，您也可以进行多轮对话。
PythonJavaNode.jsGoC#（HTTP）PHP（HTTP）curl
 
import os
from openai import OpenAI

client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"), 
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
completion = client.chat.completions.create(
    model="qwen-plus", # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=[
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': '你是谁？'}],
    )
    
print(completion.model_dump_json())
model string （必选）

模型名称。

支持的模型：通义千问大语言模型（商业版、开源版、Qwen-Long）、通义千问VL、通义千问Omni、数学模型、代码模型。

通义千问Audio暂不支持OpenAI兼容模式，仅支持DashScope方式。
具体模型名称和计费，请参见模型列表。

messages array （必选）

由历史对话组成的消息列表。

消息类型

System Message object （可选）

模型的目标或角色。如果设置系统消息，请放在messages列表的第一位。

属性

User Message object （必选）

用户发送给模型的消息。

属性

Assistant Message object （可选）

模型对用户消息的回复。

属性

Tool Message object （可选）

工具的输出信息。

属性

stream boolean （可选） 默认值为 false

是否流式输出回复。参数值：

false：模型生成完所有内容后一次性返回结果。

true：边生成边输出，即每生成一部分内容就立即输出一个片段（chunk）。您需要实时地逐个读取这些片段以获得完整的结果。

stream_options object （可选）

当启用流式输出时，可通过将本参数设置为{"include_usage": true}，在输出的最后一行显示所使用的Token数。

如果设置为false，则最后一行不显示使用的Token数。
本参数仅在设置stream为true时生效。

modalities array （可选）默认值为["text"]

输出数据的模态，仅支持 Qwen-Omni 模型指定。可选值：

["text"]：输出文本。

temperature float （可选）

采样温度，控制模型生成文本的多样性。

temperature越高，生成的文本更多样，反之，生成的文本更确定。

取值范围： [0, 2)

由于temperature与top_p均可以控制生成文本的多样性，因此建议您只设置其中一个值。更多说明，请参见Temperature 和 top_p。

temperature默认值

top_p float （可选）

核采样的概率阈值，控制模型生成文本的多样性。

top_p越高，生成的文本更多样。反之，生成的文本更确定。

取值范围：（0,1.0]

由于temperature与top_p均可以控制生成文本的多样性，因此建议您只设置其中一个值。更多说明，请参见Temperature 和 top_p。

top_p默认值

presence_penalty float （可选）

控制模型生成文本时的内容重复度。

取值范围：[-2.0, 2.0]。正数会减少重复度，负数会增加重复度。

适用场景：

较高的presence_penalty适用于要求多样性、趣味性或创造性的场景，如创意写作或头脑风暴。

较低的presence_penalty适用于要求一致性或专业术语的场景，如技术文档或其他正式文档。

presence_penalty默认值

原理介绍

示例

response_format object （可选） 默认值为{"type": "text"}

返回内容的格式。可选值：{"type": "text"}或{"type": "json_object"}。设置为{"type": "json_object"}时会输出标准格式的JSON字符串。使用方法请参见：结构化输出。

如果指定该参数为{"type": "json_object"}，您需要在System Message或User Message中指引模型输出JSON格式，如：“请按照json格式输出。”
支持的模型

max_tokens integer （可选）

本次请求返回的最大 Token 数。

max_tokens 的设置不会影响大模型的生成过程，如果模型生成的 Token 数超过max_tokens，本次请求会返回截断后的内容。
默认值和最大值都是模型的最大输出长度。关于各模型的最大输出长度，请参见模型列表。

max_tokens参数适用于需要限制字数（如生成摘要、关键词）、控制成本或减少响应时间的场景。

n integer （可选） 默认值为1

生成响应的个数，取值范围是1-4。对于需要生成多个响应的场景（如创意写作、广告文案等），可以设置较大的 n 值。

当前仅支持 qwen-plus 模型，且在传入 tools 参数时固定为1。
设置较大的 n 值不会增加输入 Token 消耗，会增加输出 Token 的消耗。
seed integer （可选）

设置seed参数会使文本生成过程更具有确定性，通常用于使模型每次运行的结果一致。

在每次模型调用时传入相同的seed值（由您指定），并保持其他参数不变，模型将尽可能返回相同的结果。

取值范围：0到231−1。

seed默认值

stop string 或 array （可选）

使用stop参数后，当模型生成的文本即将包含指定的字符串或token_id时，将自动停止生成。

您可以在stop参数中传入敏感词来控制模型的输出。

stop为array类型时，不可以将token_id和字符串同时作为元素输入，比如不可以指定stop为["你好",104307]。
tools array （可选）

可供模型调用的工具数组，可以包含一个或多个工具对象。一次Function Calling流程模型会从中选择一个工具。

目前不支持通义千问VL/Audio，也不建议用于数学和代码模型。
属性

tool_choice string 或 object （可选）默认值为 "auto"

如果您希望对于某一类问题，大模型能够采取制定好的工具选择策略（如强制使用某个工具、强制使用至少一个工具、强制不使用工具等），可以通过修改tool_choice参数来强制指定工具调用的策略。可选值：

"auto"

表示由大模型进行工具策略的选择。

"none"

如果您希望无论输入什么问题，Function Calling 都不会进行工具调用，可以设定tool_choice参数为"none"；

{"type": "function", "function": {"name": "the_function_to_call"}}

如果您希望对于某一类问题，Function Calling 能够强制调用某个工具，可以设定tool_choice参数为{"type": "function", "function": {"name": "the_function_to_call"}}，其中the_function_to_call是您指定的工具函数名称。

parallel_tool_calls boolean （可选）默认值为 false

是否开启并行工具调用。参数为true时开启，为false时不开启。并行工具调用详情请参见：并行工具调用。

translation_options object （可选）

当您使用翻译模型时需要配置的翻译参数。

属性

若您通过Python SDK调用，请通过extra_body配置。配置方式为：extra_body={"translation_options": xxx}。
enable_search boolean （可选）

模型在生成文本时是否使用互联网搜索结果进行参考。取值如下：

true：启用互联网搜索，模型会将搜索结果作为文本生成过程中的参考信息，但模型会基于其内部逻辑判断是否使用互联网搜索结果。

如果模型没有搜索互联网，建议优化Prompt，或设置search_options中的forced_search参数开启强制搜索。
false（默认）：关闭互联网搜索。

启用互联网搜索功能可能会增加 Token 的消耗。
若您通过 Python SDK调用，请通过extra_body配置。配置方式为：extra_body={"enable_search": True}。
支持的模型

search_options object （可选）

联网搜索的策略。仅当enable_search为true时生效。

属性

若您通过 Python SDK调用，请通过extra_body配置。配置方式为：extra_body={"search_options": xxx}。
X-DashScope-DataInspection string （可选）

在通义千问 API 的内容安全能力基础上，是否进一步识别输入输出内容的违规信息。取值如下：

'{"input":"cip","output":"cip"}'：进一步识别；

不设置该参数：不进一步识别。

通过 HTTP 调用时请放入请求头：-H "X-DashScope-DataInspection: {\"input\": \"cip\", \"output\": \"cip\"}"；

通过 Python SDK 调用时请通过extra_headers配置：extra_headers={'X-DashScope-DataInspection': '{"input":"cip","output":"cip"}'}。

详细使用方法请参见内容安全。

不支持通过 Node.js SDK设置。
不适用于 Qwen-VL 系列模型。
chat响应对象（非流式输出）
 
{
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "我是阿里云开发的一款超大规模语言模型，我叫通义千问。"
            },
            "finish_reason": "stop",
            "index": 0,
            "logprobs": null
        }
    ],
    "object": "chat.completion",
    "usage": {
        "prompt_tokens": 3019,
        "completion_tokens": 104,
        "total_tokens": 3123,
        "prompt_tokens_details": {
            "cached_tokens": 2048
        }
    },
    "created": 1735120033,
    "system_fingerprint": null,
    "model": "qwen-plus",
    "id": "chatcmpl-6ada9ed2-7f33-9de2-8bb0-78bd4035025a"
}
id string

本次调用的唯一标识符。

choices array

模型生成内容的数组，可以包含一个或多个choices对象。

属性

created integer

本次chat请求被创建时的时间戳。

model string

本次chat请求使用的模型名称。

object string

始终为chat.completion。

service_tier string

该参数当前固定为null。

system_fingerprint string

该参数当前固定为null。

usage object

本次chat请求使用的 Token 信息。

属性

chat响应chunk对象（流式输出）
 
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"","function_call":null,"refusal":null,"role":"assistant","tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"我是","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"来自","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"阿里","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"云的超大规模","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"语言模型，我","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"叫通义千","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"问。","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":null,"index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[{"delta":{"content":"","function_call":null,"refusal":null,"role":null,"tool_calls":null},"finish_reason":"stop","index":0,"logprobs":null}],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":null}
{"id":"chatcmpl-e30f5ae7-3063-93c4-90fe-beb5f900bd57","choices":[],"created":1735113344,"model":"qwen-plus","object":"chat.completion.chunk","service_tier":null,"system_fingerprint":null,"usage":{"completion_tokens":17,"prompt_tokens":22,"total_tokens":39,"completion_tokens_details":null,"prompt_tokens_details":{"audio_tokens":null,"cached_tokens":0}}}
id string

本次调用的唯一标识符。每个chunk对象有相同的 id。

choices array

模型生成内容的数组，可包含一个或多个choices对象。如果设置include_usage参数为true，则最后一个chunk为空。

属性

created integer

本次chat请求被创建时的时间戳。每个chunk对象有相同的时间戳。

model string

本次chat请求使用的模型名称。

object string

始终为chat.completion.chunk。

service_tier string

该参数当前固定为null。

system_fingerprintstring

该参数当前固定为null。

usage object

本次chat请求使用的Token信息。只在include_usage为true时，在最后一个chunk显示。

属性

DashScope
公有云金融云
通过HTTP调用时需配置的endpoint：

使用通义千问大语言模型：POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation

使用通义千问VL或通义千问Audio模型：POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation

您需要已获取API Key并配置API Key到环境变量。如果通过DashScope SDK进行调用，还需要安装DashScope SDK。
请求体
文本输入流式输出图像输入视频输入音频输入联网搜索工具调用异步调用文字提取
此处以单轮对话作为示例，您也可以进行多轮对话。
PythonJavaPHP（HTTP）Node.js（HTTP）C#（HTTP）Go（HTTP）curl
 
import os
import dashscope

messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': '你是谁？'}
    ]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=os.getenv('DASHSCOPE_API_KEY'),
    model="qwen-plus", # 此处以qwen-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    messages=messages,
    result_format='message'
    )
print(response)
model string （必选）

模型名称。

支持的模型：通义千问大语言模型（商业版、开源版、Qwen-Long）、通义千问VL、通义千问Audio、数学模型、代码模型

具体模型名称和计费，请参见模型列表。

messages array （必选）

由历史对话组成的消息列表。

通过HTTP调用时，请将messages 放入 input 对象中。
消息类型

temperature float （可选）

采样温度，控制模型生成文本的多样性。

temperature越高，生成的文本更多样，反之，生成的文本更确定。

取值范围： [0, 2)

通过HTTP调用时，请将 temperature 放入 parameters 对象中。
temperature默认值

top_p float （可选）

核采样的概率阈值，控制模型生成文本的多样性。

top_p越高，生成的文本更多样。反之，生成的文本更确定。

取值范围：（0,1.0]。

Java SDK中为topP。通过HTTP调用时，请将 top_p 放入 parameters 对象中。
top_p默认值

top_k integer （可选）

生成过程中采样候选集的大小。例如，取值为50时，仅将单次生成中得分最高的50个Token组成随机采样的候选集。取值越大，生成的随机性越高；取值越小，生成的确定性越高。取值为None或当top_k大于100时，表示不启用top_k策略，此时仅有top_p策略生效。

取值需要大于或等于0。

qwen-math 系列、qwen-vl 系列默认值为1，其余均为20。

Java SDK中为topK。通过HTTP调用时，请将 top_k 放入 parameters 对象中。
repetition_penalty float （可选）

模型生成时连续序列中的重复度。提高repetition_penalty时可以降低模型生成的重复度，1.0表示不做惩罚。没有严格的取值范围，只要大于0即可。

repetition_penalty默认值

Java SDK中为repetitionPenalty。通过HTTP调用时，请将 repetition_penalty 放入 parameters 对象中。
对于qwen-vl-ocr模型，repetition_penalty 的默认值为1.05，该参数对模型效果影响较大，请勿随意修改。
vl_high_resolution_images boolean （可选）默认值为 false

是否提高输入图片的默认Token上限。输入图片的默认Token上限为1280，配置为true时输入图片的Token上限为16384。

支持的模型

Java SDK不支持设置该参数。通过HTTP调用时，请将 vl_high_resolution_images 放入 parameters 对象中。
presence_penalty float （可选）

控制模型生成文本时的内容重复度。

取值范围：[-2.0, 2.0]。正数会减少重复度，负数会增加重复度。

适用场景：

较高的presence_penalty适用于要求多样性、趣味性或创造性的场景，如创意写作或头脑风暴。

较低的presence_penalty适用于要求一致性或专业术语的场景，如技术文档或其他正式文档。

presence_penalty默认值

原理介绍

示例

Java SDK不支持设置该参数。通过HTTP调用时，请将 presence_penalty 放入 parameters 对象中。
max_tokens integer （可选）

本次请求返回的最大 Token 数。

max_tokens 的设置不会影响大模型的生成过程，如果模型生成的 Token 数超过max_tokens，本次请求会返回截断后的内容。
默认值和最大值都是模型的最大输出长度。关于各模型的最大输出长度，请参见模型列表。

max_tokens参数适用于需要限制字数（如生成摘要、关键词）、控制成本或减少响应时间的场景。

Java SDK中为maxTokens（模型为通义千问VL/OCR/Audio/ASR时，Java SDK中为maxLength，在 2.18.4 版本之后支持也设置为 maxTokens）。通过HTTP调用时，请将 max_tokens 放入 parameters 对象中。
seed integer （可选）

设置seed参数会使文本生成过程更具有确定性，通常用于使模型每次运行的结果一致。

在每次模型调用时传入相同的seed值（由您指定），并保持其他参数不变，模型将尽可能返回相同的结果。

取值范围：0到231−1。

seed默认值

通过HTTP调用时，请将 seed 放入 parameters 对象中。
stream boolean （可选）

是否流式输出回复。参数值：

false（默认值）：模型生成完所有内容后一次性返回结果。

true：边生成边输出，即每生成一部分内容就立即输出一个片段（chunk）。

该参数仅支持Python SDK。通过Java SDK实现流式输出请通过streamCall接口调用；通过HTTP实现流式输出请在Header中指定X-DashScope-SSE为enable。
incremental_output boolean （可选）默认为false（QwQ 模型默认值为 true）

在流式输出模式下是否开启增量输出。参数值：

false：每次输出为当前已经生成的整个序列，最后一次输出为生成的完整结果。

 
I
I like
I like apple
I like apple.
true：增量输出，即后续输出内容不包含已输出的内容。您需要实时地逐个读取这些片段以获得完整的结果。

 
I
like
apple
.
Java SDK中为incrementalOutput。通过HTTP调用时，请将 incremental_output 放入 parameters 对象中。
response_format object （可选） 默认值为{"type": "text"}

返回内容的格式。可选值：{"type": "text"}或{"type": "json_object"}。设置为{"type": "json_object"}时会输出标准格式的JSON字符串。使用方法请参见：结构化输出。

如果指定该参数为{"type": "json_object"}，您需要在 System Message 或 User Message 中指引模型输出 JSON 格式，如：“请按照json格式输出。”
不支持通过 Java SDK 设置该参数。通过HTTP调用时，请将 response_format 放入 parameters 对象中。
支持的模型

result_format string （可选） 默认为"text"（QwQ 模型默认值为 "message"）

返回数据的格式。推荐您优先设置为"message"，可以更方便地进行多轮对话。

Java SDK中为resultFormat。通过HTTP调用时，请将 result_format 放入 parameters 对象中。
stop string 或 array （可选）

使用stop参数后，当模型生成的文本即将包含指定的字符串或token_id时，将自动停止生成。

您可以在stop参数中传入敏感词来控制模型的输出。

stop为array类型时，不可以将token_id和字符串同时作为元素输入，比如不可以指定stop为["你好",104307]。
tools array （可选）

可供模型调用的工具数组，可以包含一个或多个工具对象。一次 Function Calling 流程模型会从中选择其中一个工具。使用 tools 时需要同时指定result_format参数为"message"。无论是发起 Function Calling，还是向模型提交工具函数的执行结果，均需设置tools参数。

目前不支持通义千问VL/Audio，也不建议用于数学和代码模型。
属性

通过HTTP调用时，请将 tools 放入 parameters JSON 对象中。暂时不支持qwen-vl与qwen-audio系列模型。
tool_choice string 或 object （可选）

在使用tools参数时，用于控制模型调用指定工具。有三种取值：

"none"表示不调用工具。tools参数为空时，默认值为"none"。

"auto"表示由模型判断是否调用工具，可能调用也可能不调用。tools参数不为空时，默认值为"auto"。

object结构可以指定模型调用的工具。例如tool_choice={"type": "function", "function": {"name": "user_function"}}。

type只支持指定为"function"。

function

name表示期望被调用的工具名称，例如"get_current_time"。

Java SDK中为toolChoice。通过HTTP调用时，请将 tool_choice 放入 parameters 对象中。
translation_options object （可选）

当您使用翻译模型时需要配置的翻译参数。

属性

Java SDK 暂不支持配置该参数。通过HTTP调用时，请将 translation_options 放入 parameters 对象中。
enable_search boolean （可选）

模型在生成文本时是否使用互联网搜索结果进行参考。取值如下：

true：启用互联网搜索，模型会将搜索结果作为文本生成过程中的参考信息，但模型会基于其内部逻辑判断是否使用互联网搜索结果。

如果模型没有搜索互联网，建议优化Prompt，或设置search_options中的forced_search参数开启强制搜索。
false（默认）：关闭互联网搜索。

支持的模型

Java SDK中为enableSearch。通过HTTP调用时，请将 enable_search 放入 parameters 对象中。
启用互联网搜索功能可能会增加 Token 的消耗。
search_options object （可选）

联网搜索的策略。仅当enable_search为true时生效。

通过HTTP调用时，请将 search_options 放入 parameters 对象中。Java SDK中为searchOptions。
属性

X-DashScope-DataInspection string （可选）

在通义千问 API 的内容安全能力基础上，是否进一步识别输入输出内容的违规信息。取值如下：

'{"input":"cip","output":"cip"}'：进一步识别；

不设置该参数：不进一步识别。

通过 HTTP 调用时请放入请求头：-H "X-DashScope-DataInspection: {\"input\": \"cip\", \"output\": \"cip\"}"；

通过 Python SDK 调用时请通过headers配置：headers={'X-DashScope-DataInspection': '{"input":"cip","output":"cip"}'}。

详细使用方法请参见内容安全。

不支持通过 Java SDK 设置。
不适用于 Qwen-VL、Qwen-Audio 系列模型。
chat响应对象（流式与非流式输出格式一致）
 
{
  "status_code": 200,
  "request_id": "902fee3b-f7f0-9a8c-96a1-6b4ea25af114",
  "code": "",
  "message": "",
  "output": {
    "text": null,
    "finish_reason": null,
    "choices": [
      {
        "finish_reason": "stop",
        "message": {
          "role": "assistant",
          "content": "我是阿里云开发的一款超大规模语言模型，我叫通义千问。"
        }
      }
    ]
  },
  "usage": {
    "input_tokens": 22,
    "output_tokens": 17,
    "total_tokens": 39
  }
}